# 📚 Dictionary API (Flask + SQL Server)

## 🚀 Giới thiệu

Dictionary API là một hệ thống RESTful API hỗ trợ:

* 🔍 Tra từ điển (dictionary lookup)
* 🌍 Dịch văn bản (translate)
* 🟰 Tìm kiếm từ đồng nghĩa (thesaurus)
* 🕘 Lưu lịch sử dịch (history)
* 👤 Hỗ trợ cả user đăng nhập và guest

Hệ thống sử dụng kiến trúc **Hybrid (Database + External API)**:

* Ưu tiên dữ liệu trong database
* Nếu không có → gọi API ngoài → lưu lại (cache)

---

## 🧱 Công nghệ sử dụng

* 🐍 Python (Flask)
* 🗄 SQL Server
* 🔌 pyodbc (kết nối database)
* 🌐 External APIs:

  * Dictionary API: https://dictionaryapi.dev
  * Translate API: https://libretranslate.de

---

## 📁 Cấu trúc project

```
dictionary-api/
│── app.py
│── database.sql
│── README.md
```

---

## ⚙️ Cài đặt

### 1. Clone project

```
git clone <your-repo-url>
cd dictionary-api
```

### 2. Tạo virtual environment

```
python -m venv venv
venv\Scripts\activate   # Windows
```

### 3. Cài thư viện

```
pip install flask pyodbc requests
```

---

## 🗄️ Setup Database

### 1. Mở SQL Server

Dùng SQL Server Management Studio

### 2. Chạy file:

```
database.sql
```

---

## 🔌 Cấu hình kết nối DB

Trong `app.py`:

```python
conn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost\\SQLEXPRESS;"
    "Database=DictionaryDB;"
    "Trusted_Connection=yes;"
)
```

---

## ▶️ Chạy server

```
python app.py
```

Server chạy tại:

```
http://127.0.0.1:5000
```

---

## 📡 API Endpoints

---

### 🔍 1. Tra từ

**GET**

```
/api/word/<word>
```

**Response:**

```json
{
  "word": "hello",
  "phonetic": "/həˈləʊ/",
  "audio": "...",
  "meanings": [
    {
      "pos": "noun",
      "meaning": "a greeting",
      "example": "hello bro"
    }
  ],
  "source": "database | api"
}
```

---

### 🌍 2. Dịch

**POST**

```
/api/translate
```

**Body:**

```json
{
  "text": "hello",
  "session_id": "abc123"
}
```

**Response:**

```json
{
  "translatedText": "xin chào"
}
```

---

### 🟰 3. Tìm kiếm từ đồng nghĩa

**GET**

```
/api/thesaurus/<word>
```

**Response:**

```json
[
  {
    "word": "big",
    "synonyms": ["large", "huge", "massive"],
    "source": "database"
  }
]
```

---

### 🕘 4. Lịch sử dịch

**GET**

```
/api/history?session_id=abc123
```

**Response:**

```json
[
  {
    "source": "hello",
    "translated": "xin chào",
    "time": "2026-04-04"
  }
]
```

---

### 🔄 5. Merge history (guest → user)

**POST**

```
/api/merge-history
```

**Body:**

```json
{
  "user_id": 1,
  "session_id": "abc123"
}
```

---

### 👤 6. Register

**POST**

```
/api/register
```

---

### 🔐 6. Login

**POST**

```
/api/login
```

---

## 🧠 Tính năng nổi bật

### 🔥 Hybrid Data

* Check database trước
* Nếu không có → gọi API ngoài → lưu lại

---

### 🕘 Smart History

* Chỉ lưu lịch sử dịch
* Không lưu trùng
* Nếu trùng → cập nhật thời gian
* Giới hạn tối đa 100 bản ghi

---

### 👤 Guest & User

* Guest sử dụng `session_id`
* User sử dụng `user_id`
* Hỗ trợ merge dữ liệu khi đăng nhập

---

## 📊 Database Schema

* Users
* Words
* Meanings
* History

---

## 🔮 Hướng phát triển

* 🔐 JWT Authentication
* 🎴 Flashcard học từ vựng
* 📱 Mobile App (Android / Flutter)
* 🌐 Deploy lên VPS

---

## 👨‍💻 Tác giả

* Name: Nhóm 4 người
* Project: Dictionary API
* Subject: RESTful API

---

## ⭐ Ghi chú

Project phục vụ mục đích học tập và nghiên cứu.
