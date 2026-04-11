from flask import Flask, jsonify, request, Response
import pyodbc
import requests

from flask_cors import CORS

from deep_translator import GoogleTranslator

from gtts import gTTS
import os
import uuid
import io

from urllib.parse import quote

app = Flask(__name__)
CORS(app)

# =============================
# KẾT NỐI DATABASE
# =============================
conn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost\\SQLEXPRESS;"
    "Database=DictionaryDB;"
    "Trusted_Connection=yes;"
)

# =============================
# HELPER: TẠO URL AUDIO
# =============================
def build_tts_url(text, lang):
    return f"/api/tts?text={quote(text)}&lang={lang}"

# =============================
# HELPER: CHUYỂN AUDIO
# =============================
def extract_audio(phonetics):
    if not phonetics:
        return ""

    for p in phonetics:
        audio = p.get("audio")
        if audio and audio.strip() != "":
            return audio

    return ""

# =============================
# HELPER: LƯU LỊCH SỬ
# =============================
def save_history(user_id, session_id, source_text, translated_text):
    try:
        # insert
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO History(user_id, session_id, source_text, translated_text)
            VALUES (?, ?, ?, ?)
        """, (user_id, session_id, source_text, translated_text))
    except:
        # trùng -> update thời gian
        if user_id:
            cursor.execute("""
                UPDATE History
                SET created_at = GETDATE()
                WHERE user_id = ? 
                AND source_text = ? 
                AND translated_text = ?
            """, (user_id, source_text, translated_text))
        else:
            cursor.execute("""
                UPDATE History
                SET created_at = GETDATE()
                WHERE session_id = ? 
                AND source_text = ? 
                AND translated_text = ?
            """, (session_id, source_text, translated_text))
    # giới hạn 100 lần
    if user_id:
        cursor.execute("""
            DELETE FROM History
            WHERE user_id = ?
            AND id NOT IN (
                SELECT TOP 100 id FROM History
                WHERE user_id = ?
                ORDER BY created_at DESC
            )
        """, (user_id, user_id))
    else:
        cursor.execute("""
            DELETE FROM History
            WHERE session_id = ?
            AND id NOT IN (
                SELECT TOP 100 id FROM History
                WHERE session_id = ?
                ORDER BY created_at DESC
            )
        """, (session_id, session_id))

    conn.commit()

# =============================
# API: TRA TỪ (HYBRID)
# =============================
@app.route('/api/word/<word>', methods=['GET'])
def get_word(word):
    user_id = request.args.get('user_id')
    session_id = request.args.get('session_id')

    cursor = conn.cursor()

    # 1. CHECK DB
    cursor.execute("SELECT * FROM Words WHERE word = ?", (word,))
    w = cursor.fetchone()

    if w:
        word_id = w[0]

        cursor.execute("""
            SELECT part_of_speech, meaning, example 
            FROM Meanings WHERE word_id = ?
        """, (word_id,))

        meanings = []
        for m in cursor.fetchall():
            meanings.append({
                "pos": m[0],
                "meaning": m[1],
                "example": m[2]
            })
        
        # FALLBACK TTS nếu DB không có audio
        audio = w[3]
        if not audio:
            audio = build_tts_url(word, "en")

        result = {
            "word": w[1],
            "phonetic": w[2],
            "audio": audio,
            "meanings": meanings,
            "source": "database"
        }

        return jsonify(result)

    # 2. CALL API NGOÀI
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    res = requests.get(url)

    if res.status_code != 200:
        return jsonify({"message": "Word not found"}), 404

    data = res.json()[0]

    phonetic = data.get("phonetic", "")
    audio = extract_audio(data.get("phonetics", []))

    # FALLBACK nếu không có audio
    if not audio:
        audio = build_tts_url(word, "en")

    # LƯU WORD
    cursor.execute(
        "INSERT INTO Words(word, phonetic, audio_url) OUTPUT INSERTED.id VALUES (?, ?, ?)",
        (word, phonetic, audio)
    )
    word_id = cursor.fetchone()[0]

    meanings = []

    for m in data["meanings"]:
        pos = m["partOfSpeech"]

        for d in m["definitions"]:
            meaning = d["definition"]
            example = d.get("example", "")

            cursor.execute("""
                INSERT INTO Meanings(word_id, part_of_speech, meaning, example)
                VALUES (?, ?, ?, ?)
            """, (word_id, pos, meaning, example))

            meanings.append({
                "pos": pos,
                "meaning": meaning,
                "example": example
            })

    conn.commit()

    result = {
        "word": word,
        "phonetic": phonetic,
        "audio": audio,
        "meanings": meanings,
        "source": "api"
    }

    return jsonify(result)

# =============================
# API: TỪ ĐỒNG NGHĨA
# =============================
@app.route('/api/thesaurus/<word>', methods=['GET'])
def get_thesaurus(word):
    cursor = conn.cursor()

    # 1. CHECK DB
    cursor.execute("SELECT id FROM Words WHERE word = ?", (word,))
    w = cursor.fetchone()

    if w:
        word_id = w[0]

        cursor.execute("""
            SELECT thesaurus FROM Thesauruses
            WHERE word_id = ?
        """, (word_id,))

        data = [row[0] for row in cursor.fetchall()]

        if data:
            return jsonify({
                "word": word,
                "thesauruses": data,
                "source": "database"
            })

    # 2. GỌI API NGOÀI
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    res = requests.get(url)

    if res.status_code != 200:
        return jsonify({"message": "Word not found"}), 404

    data = res.json()[0]

    thesauruses = set()

    for m in data.get("meanings", []):
        for s in m.get("synonyms", []):
            thesauruses.add(s)
        for d in m.get("definitions", []):
            for s in d.get("synonyms", []):
                thesauruses.add(s)

    thesauruses = list(thesauruses)

    if not thesauruses:
        return jsonify({
            "word": word,
            "thesauruses": [],
            "message": "No thesauruses found"
        })

    # LƯU TỪ VÀO DB
    if not w:
        cursor.execute(
            "INSERT INTO Words(word) OUTPUT INSERTED.id VALUES (?)",
            (word,)
        )
        word_id = cursor.fetchone()[0]
    else:
        word_id = w[0]

    # LƯU TỪ ĐỒNG NGHĨA
    for s in thesauruses:
        try:
            cursor.execute("""
                INSERT INTO Thesauruses(word_id, thesaurus)
                VALUES (?, ?)
            """, (word_id, s))
        except:
            pass

    conn.commit()

    return jsonify({
        "word": word,
        "thesauruses": thesauruses,
        "source": "api"
    })

# =============================
# API: DANH SÁCH NGÔN NGỮ
# =============================
@app.route('/api/languages', methods=['GET'])
def get_languages():
    langs = GoogleTranslator(source='en', target='vi').get_supported_languages(as_dict=True)

    return jsonify(langs)

# =============================
# API: STREAMING AUDIO
# =============================
@app.route('/api/tts', methods=['GET'])
def tts():
    text = request.args.get('text', '')
    lang = request.args.get('lang', 'en')

    if not text:
        return "Missing text", 400

    try:
        tts = gTTS(text=text, lang=lang)

        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)

        return Response(
            audio_bytes,
            mimetype="audio/mpeg"
        )
    except Exception as e:
        return str(e), 500

# =============================
# API: DỊCH
# =============================
@app.route('/api/translate', methods=['POST'])
def translate():
    data = request.json
    text = data['text']
    source = data.get('source_lang', 'en')
    target = data.get('target_lang', 'vi')
    user_id = data.get('user_id')
    session_id = data.get('session_id')

    if not text:
        return jsonify({"error": "Text is required"}), 400

    cursor = conn.cursor()

    # 1. CHECK CACHE (DB trước)
    if user_id:
        cursor.execute("""
            SELECT translated_text FROM History
            WHERE user_id = ? AND source_text = ? 
            AND source_lang = ? AND target_lang = ?
        """, (user_id, text, source, target))
    else:
        cursor.execute("""
            SELECT translated_text FROM History
            WHERE session_id = ? AND source_text = ? 
            AND source_lang = ? AND target_lang = ?
        """, (session_id, text, source, target))

    row = cursor.fetchone()

    if row:
        translated_text = row[0]

        # update thời gian
        if user_id:
            cursor.execute("""
                UPDATE History SET created_at = GETDATE()
                WHERE user_id = ? AND source_text = ? 
                AND source_lang = ? AND target_lang = ?
            """, (user_id, text, source, target))
        else:
            cursor.execute("""
                UPDATE History SET created_at = GETDATE()
                WHERE session_id = ? AND source_text = ? 
                AND source_lang = ? AND target_lang = ?
            """, (session_id, text, source, target))

        conn.commit()

        return jsonify({
            "translatedText": translated_text,
            "source_audio": build_tts_url(text, source),
            "target_audio": build_tts_url(translated_text, target),
            "source": "database"
        })

    # 2. KHÔNG CÓ → GỌI GOOGLE
    try:
        translated_text = GoogleTranslator(
            source=source,
            target=target
        ).translate(text)
    except Exception as e:
        return jsonify({
            "error": "Translate failed",
            "message": str(e)
        }), 500

    # 3. LƯU DB
    try:
        cursor.execute("""
            INSERT INTO History(user_id, session_id, source_text, translated_text,
                                source_lang, target_lang)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, session_id, text, translated_text,
              source, target))
    except:
        # nếu trùng thì update time
        if user_id:
            cursor.execute("""
                UPDATE History SET created_at = GETDATE()
                WHERE user_id = ? AND source_text = ? 
                AND source_lang = ? AND target_lang = ?
            """, (user_id, text, source, target))
        else:
            cursor.execute("""
                UPDATE History SET created_at = GETDATE()
                WHERE session_id = ? AND source_text = ? 
                AND source_lang = ? AND target_lang = ?
            """, (session_id, text, source, target))

    # 4. GIỚI HẠN 100 lần
    if user_id:
        cursor.execute("""
            DELETE FROM History
            WHERE user_id = ?
            AND id NOT IN (
                SELECT TOP 100 id FROM History
                WHERE user_id = ?
                ORDER BY created_at DESC
            )
        """, (user_id, user_id))
    else:
        cursor.execute("""
            DELETE FROM History
            WHERE session_id = ?
            AND id NOT IN (
                SELECT TOP 100 id FROM History
                WHERE session_id = ?
                ORDER BY created_at DESC
            )
        """, (session_id, session_id))

    conn.commit()

    return jsonify({
        "translatedText": translated_text,
        "source_audio": build_tts_url(text, source),
        "target_audio": build_tts_url(translated_text, target),
        "source": "api"
    })

# =============================
# API: REGISTER
# =============================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data['username']
    password = data['password']

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Users(username, password) VALUES (?, ?)",
        (username, password)
    )
    conn.commit()

    return jsonify({"message": "Register success"})

# =============================
# API: LOGIN
# =============================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data['username']
    password = data['password']

    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM Users WHERE username = ? AND password = ?",
        (username, password)
    )

    user = cursor.fetchone()

    if user:
        return jsonify({
            "message": "Login success",
            "user_id": user[0]
        })
    else:
        return jsonify({"message": "Login failed"}), 401

# =============================
# API: HISTORY
# =============================
@app.route('/api/history', methods=['GET'])
def get_history():
    user_id = request.args.get('user_id')
    session_id = request.args.get('session_id')

    cursor = conn.cursor()

    if user_id:
        cursor.execute("""
            SELECT source_text, translated_text, created_at, source_lang, target_lang
            FROM History
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT source_text, translated_text, created_at, source_lang, target_lang
            FROM History
            WHERE session_id = ?
            ORDER BY created_at DESC
        """, (session_id,))

    results = []
    for row in cursor.fetchall():
        results.append({
            "source_text": row[0],
            "translated_text": row[1],
            "time": str(row[2]),
            "source_lang": row[3],
            "target_lang": row[4],
            "source_audio": build_tts_url(row[0], row[3]),
            "target_audio": build_tts_url(row[1], row[4])
        })

    return jsonify(results)

# =============================
# API: MERGE HISTORY
# =============================
@app.route('/api/merge-history', methods=['POST'])
def merge_history():
    data = request.json
    user_id = data['user_id']
    session_id = data['session_id']

    cursor = conn.cursor()

    # lấy history guest
    cursor.execute("""
        SELECT source_text, translated_text, source_lang, target_lang
        FROM History
        WHERE session_id = ?
    """, (session_id,))

    guest_data = cursor.fetchall()

    for row in guest_data:
        source = row[0]
        translated = row[1]
        source_lang = row[2]
        target_lang = row[3]

        try:
            # thử insert vào user
            cursor.execute("""
                INSERT INTO History(user_id, source_text, translated_text, source_lang, target_lang)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, source, translated, source_lang, target_lang))
        except:
            # nếu trùng → update time
            cursor.execute("""
                UPDATE History
                SET created_at = GETDATE()
                WHERE user_id = ?
                AND source_text = ?
                AND translated_text = ?
                AND source_lang = ?
                AND target_lang = ?
            """, (user_id, source, translated, source_lang, target_lang))

    # xóa history guest
    cursor.execute("""
        DELETE FROM History WHERE session_id = ?
    """, (session_id,))

    cursor.execute("""
    DELETE FROM History
    WHERE user_id = ?
    AND id NOT IN (
        SELECT TOP 100 id FROM History
        WHERE user_id = ?
        ORDER BY created_at DESC
    )
    """, (user_id, user_id))

    conn.commit()

    return jsonify({"message": "Merge success"})

# =============================
# RUN SERVER
# =============================
if __name__ == '__main__':
    app.run(debug=True)