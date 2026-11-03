from app import calculate_score


def test_calculate_score_awards_marks_for_correct_answers_only():
    questions = [
        {"question_id": 1, "correct_answer": "A"},
        {"question_id": 2, "correct_answer": "C"},
        {"question_id": 3, "correct_answer": "C"},
    ]
    answers = {"1": "A", "2": "B", "3": "C", "unexpected": "A"}
    assert calculate_score(questions, answers, 2) == 4


def test_calculate_score_with_no_answers_is_zero():
    assert calculate_score([{"question_id": 1, "correct_answer": "A"}], {}, 3) == 0
