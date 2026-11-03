CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin','student') NOT NULL DEFAULT 'student',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exams (
    exam_id INT AUTO_INCREMENT PRIMARY KEY,
    exam_name VARCHAR(180) NOT NULL,
    description TEXT,
    duration_minutes SMALLINT UNSIGNED NOT NULL,
    marks_per_question SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    starts_at DATETIME NULL,
    ends_at DATETIME NULL,
    is_published TINYINT(1) NOT NULL DEFAULT 0,
    created_by INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_exams_creator FOREIGN KEY (created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS questions (
    question_id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_answer ENUM('A','B','C','D') NOT NULL,
    CONSTRAINT fk_questions_exam FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS results (
    result_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    exam_id INT NOT NULL,
    score INT UNSIGNED NOT NULL,
    total_marks INT UNSIGNED NOT NULL,
    is_published TINYINT(1) NOT NULL DEFAULT 0,
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_exam UNIQUE (student_id, exam_id),
    CONSTRAINT fk_results_student FOREIGN KEY (student_id) REFERENCES users(user_id),
    CONSTRAINT fk_results_exam FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS result_answers (
    result_id INT NOT NULL,
    question_id INT NOT NULL,
    selected_answer ENUM('A','B','C','D') NULL,
    PRIMARY KEY (result_id, question_id),
    CONSTRAINT fk_result_answers_result FOREIGN KEY (result_id) REFERENCES results(result_id) ON DELETE CASCADE,
    CONSTRAINT fk_result_answers_question FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE
);
