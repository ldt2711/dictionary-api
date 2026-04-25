-- =============================
-- DATABASE
-- =============================
CREATE DATABASE DictionaryDB
GO

USE DictionaryDB
GO

-- =============================
-- TABLE: Words
-- =============================
CREATE TABLE Words (
    id INT IDENTITY PRIMARY KEY,
    word NVARCHAR(100) UNIQUE,
    phonetic NVARCHAR(100),
    audio_url NVARCHAR(255)
)

-- =============================
-- TABLE: Meanings
-- =============================
CREATE TABLE Meanings (
    id INT IDENTITY PRIMARY KEY,
    word_id INT,
    part_of_speech NVARCHAR(50),
    meaning NVARCHAR(MAX),
    example NVARCHAR(MAX),
    FOREIGN KEY (word_id) REFERENCES Words(id)
)

-- =============================
-- TABLE: Thesauruses
-- =============================
CREATE TABLE Thesauruses (
    id INT IDENTITY PRIMARY KEY,
    word_id INT,
    thesaurus NVARCHAR(100),
    relation_type TINYINT DEFAULT 0, -- cột relation_type (0: Synonym, 1: Antonym)

    FOREIGN KEY (word_id) REFERENCES Words(id)
)

-- =============================
-- TABLE: Users
-- =============================
CREATE TABLE Users (
    id INT IDENTITY PRIMARY KEY,
    username NVARCHAR(50) UNIQUE,
    password NVARCHAR(255),
    created_at DATETIME DEFAULT GETDATE()
)

-- =============================
-- TABLE: History
-- =============================
CREATE TABLE History (
    id INT IDENTITY PRIMARY KEY,
    user_id INT NULL,
    session_id NVARCHAR(100),

    source_text NVARCHAR(500),
    translated_text NVARCHAR(500),
    source_lang NVARCHAR(10), 
    target_lang NVARCHAR(10),

    created_at DATETIME DEFAULT GETDATE(),

    FOREIGN KEY (user_id) REFERENCES Users(id)
)
GO

-- chống trùng từ cho USER
CREATE UNIQUE INDEX uq_user_history 
ON History(user_id, source_text, source_lang, target_lang)
WHERE user_id IS NOT NULL

-- chống trùng từ cho GUEST
CREATE UNIQUE INDEX uq_session_history 
ON History(session_id, source_text, source_lang, target_lang)
WHERE session_id IS NOT NULL

-- =============================
-- INDEX (tăng tốc search)
-- =============================
CREATE INDEX idx_word ON Words(word)
CREATE INDEX idx_thes_word_type ON Thesauruses(word_id, relation_type);

-- Sử dụng những dòng này nếu đã tạo sẵn bảng
-- Thêm cột relation_type (0: Synonym, 1: Antonym)
-- ALTER TABLE Thesauruses ADD relation_type TINYINT DEFAULT 0;
-- GO

-- -- Cập nhật INDEX để tìm kiếm nhanh hơn theo loại
-- CREATE INDEX idx_thes_word_type ON Thesauruses(word_id, relation_type);