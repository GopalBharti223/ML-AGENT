"""
Multi-Category High-Curiosity Quiz Database for LR Atlas YouTube Channel.
Categories:
- Tech & AI
- Sports & Legends
- Wealth & Superpowers
- World Wonders & Geography
- Entertainment & Pop Culture
"""

QUIZ_TOPICS = [
    {
        "id": "quiz_01_japan",
        "category": "GEOGRAPHY & WONDERS",
        "question": "Which country has over 6,800 islands and the world's fastest bullet trains?",
        "clue": "Home to Mount Fuji and famous for cherry blossoms",
        "options": [
            {"letter": "A", "name": "INDONESIA", "code": "id", "correct": False},
            {"letter": "B", "name": "JAPAN", "code": "jp", "correct": True},
            {"letter": "C", "name": "SOUTH KOREA", "code": "kr", "correct": False},
            {"letter": "D", "name": "NEW ZEALAND", "code": "nz", "correct": False},
        ],
        "narration_hook": "Can you guess this country in six seconds? It has over six thousand islands and the fastest bullet trains in the world.",
        "narration_countdown": "Six seconds on the clock. Drop your guess in the comments right now.",
        "narration_reveal": "Time is up! The answer is B, Japan! Subscribe for daily brain quizzes and see you tomorrow!",
        "youtube_title": "Only 5% Can Guess This Country in 6 Seconds! 🌍🧠 #Shorts #Quiz #Geography",
        "tags": ["shorts", "quiz", "geography", "trivia", "japan", "guess the country", "daily quiz", "LR Atlas", "IQ test"]
    },
    {
        "id": "quiz_02_ai_chips",
        "category": "TECH & AI GIANTS",
        "question": "Which country manufactures over 90% of the world's most advanced AI chips?",
        "clue": "Home to TSMC, powering Apple, Nvidia, and Google AI",
        "options": [
            {"letter": "A", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "B", "name": "SOUTH KOREA", "code": "kr", "correct": False},
            {"letter": "C", "name": "TAIWAN", "code": "tw", "correct": True},
            {"letter": "D", "name": "JAPAN", "code": "jp", "correct": False},
        ],
        "narration_hook": "Which country secretly manufactures over ninety percent of the world's advanced AI chips?",
        "narration_countdown": "Six seconds to choose. Put your answer in the comments now.",
        "narration_reveal": "Time is up! It's C, Taiwan! Home to TSMC. Subscribe for your daily trivia quiz!",
        "youtube_title": "Who Makes 90% of the World's AI Chips? 💻🤖 #Shorts #Tech #Quiz #AI",
        "tags": ["shorts", "tech quiz", "ai chips", "nvidia", "taiwan", "tsmc", "semiconductors", "daily quiz", "LR Atlas"]
    },
    {
        "id": "quiz_03_ballon_dor",
        "category": "SPORTS & LEGENDS",
        "question": "Which country has won the most FIFA Ballon d'Or trophies in football history?",
        "clue": "Home to Lionel Messi and Diego Maradona",
        "options": [
            {"letter": "A", "name": "BRAZIL", "code": "br", "correct": False},
            {"letter": "B", "name": "ARGENTINA", "code": "ar", "correct": True},
            {"letter": "C", "name": "PORTUGAL", "code": "pt", "correct": False},
            {"letter": "D", "name": "FRANCE", "code": "fr", "correct": False},
        ],
        "narration_hook": "Which country holds the all-time record for the most FIFA Ballon d'Or trophies?",
        "narration_countdown": "Six seconds on the clock. Football fans, make your guess below.",
        "narration_reveal": "Time is up! It's B, Argentina, with eight from Messi alone! Subscribe for daily quizzes!",
        "youtube_title": "Which Country Won the Most Ballon d'Ors? ⚽🏆 #Shorts #Football #Messi #Quiz",
        "tags": ["shorts", "football quiz", "soccer", "messi", "argentina", "ballon d or", "ronaldo", "daily quiz", "LR Atlas"]
    },
    {
        "id": "quiz_04_gold_reserves",
        "category": "WEALTH & SUPERPOWERS",
        "question": "Which country holds over 8,100 metric tonnes of gold reserves in Fort Knox?",
        "clue": "More than the next three largest countries combined",
        "options": [
            {"letter": "A", "name": "GERMANY", "code": "de", "correct": False},
            {"letter": "B", "name": "SWITZERLAND", "code": "ch", "correct": False},
            {"letter": "C", "name": "UNITED STATES", "code": "us", "correct": True},
            {"letter": "D", "name": "CHINA", "code": "cn", "correct": False},
        ],
        "narration_hook": "Which country guards over eight thousand one hundred tonnes of gold in its vaults?",
        "narration_countdown": "Six seconds on the clock. Can you name this financial titan?",
        "narration_reveal": "Time is up! It's C, the United States, guarding over eight thousand tonnes! Subscribe for daily trivia!",
        "youtube_title": "Who Owns the World's Largest Gold Vault? 💰🥇 #Shorts #Gold #Wealth #Quiz",
        "tags": ["shorts", "gold reserves", "fort knox", "finance quiz", "economy", "billionaires", "daily quiz", "LR Atlas"]
    },
    {
        "id": "quiz_05_largest_desert",
        "category": "GEOGRAPHY & WONDERS",
        "question": "What is the largest desert on Planet Earth by total land area?",
        "clue": "A polar desert covered in ice, not sand",
        "options": [
            {"letter": "A", "name": "SAHARA DESERT", "code": "eg", "correct": False},
            {"letter": "B", "name": "ANTARCTICA", "code": "aq", "correct": True},
            {"letter": "C", "name": "ARABIAN DESERT", "code": "sa", "correct": False},
            {"letter": "D", "name": "GOBI DESERT", "code": "mn", "correct": False},
        ],
        "narration_hook": "Ninety percent get this wrong! What is the largest desert on planet Earth?",
        "narration_countdown": "Six seconds to answer. It is not what you think!",
        "narration_reveal": "Time is up! It's B, Antarctica! Deserts are defined by low rainfall, not sand! Subscribe for daily brain trivia!",
        "youtube_title": "90% Fail This Quiz: Largest Desert on Earth? 🏜️❄️ #Shorts #Geography #Trivia",
        "tags": ["shorts", "largest desert", "antarctica", "sahara", "earth facts", "mind blown", "daily quiz", "LR Atlas"]
    }
]

def get_quiz_by_id(quiz_id):
    for q in QUIZ_TOPICS:
        if q["id"] == quiz_id:
            return q
    return QUIZ_TOPICS[0]
