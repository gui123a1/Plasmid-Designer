-- 数据库初始化脚本
-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建序列
CREATE SEQUENCE IF NOT EXISTS users_id_seq;
CREATE SEQUENCE IF NOT EXISTS designs_id_seq;
CREATE SEQUENCE IF NOT EXISTS vectors_id_seq;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- 设计任务表
CREATE TABLE IF NOT EXISTS designs (
    id SERIAL PRIMARY KEY,
    design_id VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id),
    input_sequence TEXT NOT NULL,
    optimized_sequence TEXT,
    sequence_name VARCHAR(200),
    sequence_type VARCHAR(20),
    vector_id VARCHAR(100),
    cloning_method VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    cai FLOAT,
    gc_content FLOAT,
    final_length INTEGER,
    validation_passed BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 引物表
CREATE TABLE IF NOT EXISTS primers (
    id SERIAL PRIMARY KEY,
    design_id INTEGER REFERENCES designs(id) ON DELETE CASCADE,
    name VARCHAR(100),
    sequence TEXT,
    full_sequence TEXT,
    tm FLOAT,
    gc_content FLOAT,
    length INTEGER,
    overhang VARCHAR(50),
    notes TEXT
);

-- 载体表
CREATE TABLE IF NOT EXISTS vectors (
    id SERIAL PRIMARY KEY,
    vector_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    source VARCHAR(100),
    vector_type VARCHAR(50),
    host TEXT[],
    antibiotic_resistance TEXT[],
    copy_number VARCHAR(50),
    sequence TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 载体特征表
CREATE TABLE IF NOT EXISTS vector_features (
    id SERIAL PRIMARY KEY,
    vector_id INTEGER REFERENCES vectors(id) ON DELETE CASCADE,
    name VARCHAR(200),
    feature_type VARCHAR(50),
    start_pos INTEGER,
    end_pos INTEGER,
    strand VARCHAR(1),
    description TEXT
);

-- 批量任务表
CREATE TABLE IF NOT EXISTS batch_jobs (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id),
    total INTEGER,
    completed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 设计警告表
CREATE TABLE IF NOT EXISTS design_warnings (
    id SERIAL PRIMARY KEY,
    design_id INTEGER REFERENCES designs(id) ON DELETE CASCADE,
    warning_type VARCHAR(100),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 设计错误表
CREATE TABLE IF NOT EXISTS design_errors (
    id SERIAL PRIMARY KEY,
    design_id INTEGER REFERENCES designs(id) ON DELETE CASCADE,
    error_type VARCHAR(100),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_designs_user_id ON designs(user_id);
CREATE INDEX IF NOT EXISTS idx_designs_status ON designs(status);
CREATE INDEX IF NOT EXISTS idx_designs_created_at ON designs(created_at);
CREATE INDEX IF NOT EXISTS idx_vectors_vector_id ON vectors(vector_id);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_user_id ON batch_jobs(user_id);

-- 插入默认管理员（密码: admin123，请在生产环境中修改）
-- INSERT INTO users (email, username, password_hash, is_admin)
-- VALUES ('admin@plasmid.local', 'admin', '$2b$12$hashed_password_here', true);
