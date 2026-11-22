"""
Multi-Category High-Curiosity Quiz Database for LR Atlas YouTube Channel.
Covers 20+ viral topics spanning Tech, Sports, Wealth, Geography, Nature, and Pop Culture.
"""

QUIZ_TOPICS = [
    # --- PREVIOUS / ARCHIVED TOPICS ---
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
        "tags": ["shorts", "quiz", "geography", "trivia", "japan", "guess the country", "daily quiz", "LR Atlas", "IQ test"],
        "voice": "en-US-BrianNeural"
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
        "tags": ["shorts", "tech quiz", "ai chips", "nvidia", "taiwan", "tsmc", "semiconductors", "daily quiz", "LR Atlas"],
        "voice": "en-US-ChristopherNeural"
    },
    {
        "id": "quiz_03_ballon_dor",
        "category": "SPORTS & LEGENDS",
        "question": "Which country has won the most FIFA Ballon d'Or trophies in football history?",
        "clue": "Home to Lionel Messi and Diego Maradona",
        "options": [
            {"letter": "A", "name": "BRAZIL", "code": "br", "correct": False},
            {"letter": "B", "name": "ARGENTINA", "code": "ar", "correct": True},
            {"letter": "C", "name": "GERMANY", "code": "de", "correct": False},
            {"letter": "D", "name": "FRANCE", "code": "fr", "correct": False},
        ],
        "narration_hook": "Which country holds the all-time record for the most FIFA Ballon d'Or trophies?",
        "narration_countdown": "Six seconds on the clock. Football fans, make your guess below.",
        "narration_reveal": "Time is up! It's B, Argentina, with eight from Messi alone! Subscribe for daily quizzes!",
        "youtube_title": "Which Country Won the Most Ballon d'Ors? ⚽🏆 #Shorts #Football #Messi #Quiz",
        "tags": ["shorts", "football quiz", "soccer", "messi", "argentina", "ballon d or", "ronaldo", "daily quiz", "LR Atlas"],
        "voice": "en-US-GuyNeural"
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
        "tags": ["shorts", "gold reserves", "fort knox", "finance quiz", "economy", "billionaires", "daily quiz", "LR Atlas"],
        "voice": "en-US-BrianNeural"
    },
    {
        "id": "quiz_06_natural_lakes",
        "category": "EARTH & WONDERS",
        "question": "Which country contains over 50% of all natural lakes in the entire world?",
        "clue": "Has over 2 million lakes and the longest coastline on Earth",
        "options": [
            {"letter": "A", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "B", "name": "RUSSIA", "code": "ru", "correct": False},
            {"letter": "C", "name": "CANADA", "code": "ca", "correct": True},
            {"letter": "D", "name": "AUSTRALIA", "code": "au", "correct": False},
        ],
        "narration_hook": "Ninety percent get this wrong! Which country contains half of all natural lakes on Earth?",
        "narration_countdown": "Six seconds to answer. Think big and drop your guess now.",
        "narration_reveal": "Time is up! It's C, Canada! With over two million lakes! Subscribe for daily trivia!",
        "youtube_title": "90% Fail: Which Country Has Half of Earth's Lakes? 🌊🏔️ #Shorts #Geography #Quiz",
        "tags": ["shorts", "canada", "natural lakes", "earth facts", "geography quiz", "nature", "daily quiz", "LR Atlas"],
        "voice": "en-GB-RyanNeural"
    },
    {
        "id": "quiz_07_youtube_subscribers",
        "category": "POP CULTURE & GIANTS",
        "question": "Which country is home to the most subscribed YouTube channel in the world?",
        "clue": "Home to music record giant T-Series with 280M+ subscribers",
        "options": [
            {"letter": "A", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "B", "name": "INDIA", "code": "in", "correct": True},
            {"letter": "C", "name": "UNITED KINGDOM", "code": "gb", "correct": False},
            {"letter": "D", "name": "JAPAN", "code": "jp", "correct": False},
        ],
        "narration_hook": "Which country is home to the most subscribed YouTube channel on the planet?",
        "narration_countdown": "Six seconds on the clock. Can you name this digital superpower?",
        "narration_reveal": "Time is up! It's B, India! Home to T-Series with over two hundred eighty million subscribers! Subscribe for daily quizzes!",
        "youtube_title": "Who Has the #1 Most Subscribed YouTube Channel? 📱🔥 #Shorts #YouTube #Quiz",
        "tags": ["shorts", "youtube subscribers", "tseries", "mrbeast", "india", "pop culture", "daily quiz", "LR Atlas"],
        "voice": "en-GB-SoniaNeural"
    },

    # --- 10-DAY SERIES (20 NEW HIGH-CURIOSITY DROPS) ---

    # DAY 1: Tuesday, Nov 24, 2026
    {
        "id": "quiz_10day_01_burj_khalifa",
        "day": 1,
        "slot": "1:00 PM IST",
        "category": "ARCHITECTURE & MEGASTRUCTURES",
        "question": "Which country built the tallest skyscraper ever created, standing 828 meters tall?",
        "clue": "Home to the Burj Khalifa and the iconic Palm Islands",
        "options": [
            {"letter": "A", "name": "SAUDI ARABIA", "code": "sa", "correct": False},
            {"letter": "B", "name": "UNITED ARAB EMIRATES", "code": "ae", "correct": True},
            {"letter": "C", "name": "CHINA", "code": "cn", "correct": False},
            {"letter": "D", "name": "UNITED STATES", "code": "us", "correct": False},
        ],
        "narration_hook": "Which country built the tallest building ever made by humanity, standing over 828 meters high?",
        "narration_countdown": "Six seconds on the clock. Drop your guess in the comments right now.",
        "narration_reveal": "Time is up! It's B, the UAE, home to the breathtaking Burj Khalifa! Subscribe for daily brain quizzes!",
        "youtube_title": "Who Built the Tallest Skyscraper on Earth? 🏙️🇦🇪 #Shorts #Quiz #Trivia",
        "tags": ["shorts", "burj khalifa", "dubai", "uae", "architecture", "megastructures", "daily quiz", "LR Atlas"],
        "voice": "en-US-BrianNeural",
        "schedule_time": "2026-11-24T07:30:00Z",
        "schedule_label": "Tuesday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_02_fifa_world_cups",
        "day": 1,
        "slot": "7:30 PM IST",
        "category": "SPORTS & FOOTBALL",
        "question": "Which country has won the FIFA World Cup 5 times, more than any other nation?",
        "clue": "The legendary football homeland of Pelé, Ronaldo, and Neymar",
        "options": [
            {"letter": "A", "name": "GERMANY", "code": "de", "correct": False},
            {"letter": "B", "name": "ARGENTINA", "code": "ar", "correct": False},
            {"letter": "C", "name": "BRAZIL", "code": "br", "correct": True},
            {"letter": "D", "name": "FRANCE", "code": "fr", "correct": False},
        ],
        "narration_hook": "Which country has won the FIFA World Cup five times, more than any other nation in history?",
        "narration_countdown": "Six seconds on the clock. Football fans, make your call below.",
        "narration_reveal": "Time is up! It's C, Brazil, the undisputed kings of the World Cup! Subscribe for daily quizzes!",
        "youtube_title": "Which Country Won the Most FIFA World Cups? ⚽🏆 #Shorts #Football #Quiz",
        "tags": ["shorts", "world cup", "brazil", "football quiz", "soccer", "pele", "ronaldo", "daily quiz", "LR Atlas"],
        "voice": "en-US-GuyNeural",
        "schedule_time": "2026-11-24T14:00:00Z",
        "schedule_label": "Tuesday 7:30 PM IST"
    },

    # DAY 2: Wednesday, Nov 25, 2026
    {
        "id": "quiz_10day_03_mount_everest",
        "day": 2,
        "slot": "1:00 PM IST",
        "category": "GEOGRAPHY & WONDERS",
        "question": "Which country is home to Mount Everest, the highest mountain on Planet Earth?",
        "clue": "Soaring 8,848 meters high in the majestic Himalayas",
        "options": [
            {"letter": "A", "name": "INDIA", "code": "in", "correct": False},
            {"letter": "B", "name": "CHINA", "code": "cn", "correct": False},
            {"letter": "C", "name": "NEPAL", "code": "np", "correct": True},
            {"letter": "D", "name": "PAKISTAN", "code": "pk", "correct": False},
        ],
        "narration_hook": "Ninety-five percent get this wrong! Which country is home to Mount Everest, the highest peak on Earth?",
        "narration_countdown": "Six seconds to answer. Drop your answer in the comments now.",
        "narration_reveal": "Time is up! It's C, Nepal, home to the roof of the world! Subscribe for daily brain trivia!",
        "youtube_title": "95% Don't Know Which Country Owns Mount Everest! 🏔️🚩 #Shorts #Geography #Quiz",
        "tags": ["shorts", "mount everest", "nepal", "geography quiz", "himalayas", "earth facts", "daily quiz", "LR Atlas"],
        "voice": "en-GB-RyanNeural",
        "schedule_time": "2026-11-25T07:30:00Z",
        "schedule_label": "Wednesday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_04_autobahn",
        "day": 2,
        "slot": "7:30 PM IST",
        "category": "SUPERCARS & SPEED",
        "question": "Which country is world-famous for having public highways with NO speed limit?",
        "clue": "Home to Porsche, BMW, Mercedes, and the legendary Autobahn",
        "options": [
            {"letter": "A", "name": "GERMANY", "code": "de", "correct": True},
            {"letter": "B", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "C", "name": "FRANCE", "code": "fr", "correct": False},
            {"letter": "D", "name": "JAPAN", "code": "jp", "correct": False},
        ],
        "narration_hook": "Which country is world-famous for having superhighways with absolutely zero speed limits?",
        "narration_countdown": "Six seconds on the clock. Car lovers, can you name this automotive beast?",
        "narration_reveal": "Time is up! It's A, Germany, home to the legendary Autobahn! Subscribe for daily brain trivia!",
        "youtube_title": "The Country With NO Speed Limits! 🏎️💨 #Shorts #Supercars #Cars #Quiz",
        "tags": ["shorts", "autobahn", "germany", "supercars", "porsche", "bmw", "cars quiz", "daily quiz", "LR Atlas"],
        "voice": "en-US-ChristopherNeural",
        "schedule_time": "2026-11-25T14:00:00Z",
        "schedule_label": "Wednesday 7:30 PM IST"
    },

    # DAY 3: Thursday, Nov 26, 2026
    {
        "id": "quiz_10day_05_no_mosquitoes",
        "day": 3,
        "slot": "1:00 PM IST",
        "category": "SCIENCE & NATURE",
        "question": "Which country on Earth has completely ZERO mosquitoes living within its borders?",
        "clue": "A volcanic Nordic island powered entirely by clean geothermal energy",
        "options": [
            {"letter": "A", "name": "NORWAY", "code": "no", "correct": False},
            {"letter": "B", "name": "ICELAND", "code": "is", "correct": True},
            {"letter": "C", "name": "SWITZERLAND", "code": "ch", "correct": False},
            {"letter": "D", "name": "CANADA", "code": "ca", "correct": False},
        ],
        "narration_hook": "Can you guess the only country on Earth that has completely zero mosquitoes?",
        "narration_countdown": "Six seconds to answer. Think cold and drop your guess below.",
        "narration_reveal": "Time is up! It's B, Iceland! Its unique rapid freeze cycles stop mosquitoes from breeding! Subscribe for daily trivia!",
        "youtube_title": "The Only Country on Earth With ZERO Mosquitoes! 🦟❄️ #Shorts #Science #Quiz",
        "tags": ["shorts", "iceland", "mosquitoes", "science facts", "nature quiz", "mind blown", "daily quiz", "LR Atlas"],
        "voice": "en-GB-SoniaNeural",
        "schedule_time": "2026-11-26T07:30:00Z",
        "schedule_label": "Thursday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_06_spices_capital",
        "day": 3,
        "slot": "7:30 PM IST",
        "category": "COMMERCE & HERITAGE",
        "question": "Which country produces over 70% of the world's spices and invented the game of Chess?",
        "clue": "Home to the world's largest spice markets and oldest civilization",
        "options": [
            {"letter": "A", "name": "INDONESIA", "code": "id", "correct": False},
            {"letter": "B", "name": "CHINA", "code": "cn", "correct": False},
            {"letter": "C", "name": "INDIA", "code": "in", "correct": True},
            {"letter": "D", "name": "BANGLADESH", "code": "bd", "correct": False},
        ],
        "narration_hook": "Which country produces over seventy percent of the world's spices and invented chess?",
        "narration_countdown": "Six seconds on the clock. Can you name this ancient spice empire?",
        "narration_reveal": "Time is up! It's C, India, producing over seventy percent of global spices! Subscribe for daily quizzes!",
        "youtube_title": "Which Country Produces 70% of All Spices? 🌶️🍛 #Shorts #Trivia #Quiz #India",
        "tags": ["shorts", "india", "spices", "chess", "history quiz", "food trivia", "daily quiz", "LR Atlas"],
        "voice": "en-US-BrianNeural",
        "schedule_time": "2026-11-26T14:00:00Z",
        "schedule_label": "Thursday 7:30 PM IST"
    },

    # DAY 4: Friday, Nov 27, 2026
    {
        "id": "quiz_10day_07_ev_superpower",
        "day": 4,
        "slot": "1:00 PM IST",
        "category": "GREEN TECH & FUTURE",
        "question": "Which country leads the world with over 80% of all new cars sold being pure electric?",
        "clue": "A Scandinavian powerhouse famous for majestic fjords and green energy",
        "options": [
            {"letter": "A", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "B", "name": "CHINA", "code": "cn", "correct": False},
            {"letter": "C", "name": "NORWAY", "code": "no", "correct": True},
            {"letter": "D", "name": "GERMANY", "code": "de", "correct": False},
        ],
        "narration_hook": "Which country has over eighty percent of all new cars sold powered by pure electricity?",
        "narration_countdown": "Six seconds to choose. Drop your guess in the comments right now.",
        "narration_reveal": "Time is up! It's C, Norway, the global leader in electric vehicles! Subscribe for daily brain trivia!",
        "youtube_title": "Where 80% of All Cars Are Pure Electric! ⚡🚗 #Shorts #EV #Tech #Quiz",
        "tags": ["shorts", "electric cars", "norway", "ev", "tesla", "green tech", "future", "daily quiz", "LR Atlas"],
        "voice": "en-US-GuyNeural",
        "schedule_time": "2026-11-27T07:30:00Z",
        "schedule_label": "Friday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_08_bullet_trains",
        "day": 4,
        "slot": "7:30 PM IST",
        "category": "MEGA INFRASTRUCTURE",
        "question": "Which country built over 45,000 km of high-speed rail, more than the rest of Earth combined?",
        "clue": "Connecting hundreds of mega-cities with trains cruising at 350 km/h",
        "options": [
            {"letter": "A", "name": "JAPAN", "code": "jp", "correct": False},
            {"letter": "B", "name": "FRANCE", "code": "fr", "correct": False},
            {"letter": "C", "name": "GERMANY", "code": "de", "correct": False},
            {"letter": "D", "name": "CHINA", "code": "cn", "correct": True},
        ],
        "narration_hook": "Which country built over forty-five thousand kilometers of high-speed bullet train rail?",
        "narration_countdown": "Six seconds on the clock. It has more high-speed rail than all other nations combined!",
        "narration_reveal": "Time is up! It's D, China, operating over two-thirds of the world's high-speed rail! Subscribe for daily quizzes!",
        "youtube_title": "Who Built More Bullet Trains Than the Rest of Earth? 🚄⚡ #Shorts #Tech #Quiz",
        "tags": ["shorts", "bullet train", "china", "high speed rail", "trains", "engineering", "daily quiz", "LR Atlas"],
        "voice": "en-GB-RyanNeural",
        "schedule_time": "2026-11-27T14:00:00Z",
        "schedule_label": "Friday 7:30 PM IST"
    },

    # DAY 5: Saturday, Nov 28, 2026
    {
        "id": "quiz_10day_09_most_visited",
        "day": 5,
        "slot": "1:00 PM IST",
        "category": "TRAVEL & TOURISM",
        "question": "Which country is the #1 most visited in the world, welcoming 100M+ tourists each year?",
        "clue": "Home to the Eiffel Tower, the Louvre Museum, and world-class wine",
        "options": [
            {"letter": "A", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "B", "name": "SPAIN", "code": "es", "correct": False},
            {"letter": "C", "name": "FRANCE", "code": "fr", "correct": True},
            {"letter": "D", "name": "JAPAN", "code": "jp", "correct": False},
        ],
        "narration_hook": "Which country attracts over one hundred million international tourists every single year?",
        "narration_countdown": "Six seconds on the clock. Can you name the tourism capital of the world?",
        "narration_reveal": "Time is up! It's C, France, the most visited country on planet Earth! Subscribe for daily trivia!",
        "youtube_title": "#1 Most Visited Country in the World! ✈️🗼 #Shorts #Travel #Quiz #France",
        "tags": ["shorts", "france", "paris", "most visited", "travel quiz", "eiffel tower", "daily quiz", "LR Atlas"],
        "voice": "en-GB-SoniaNeural",
        "schedule_time": "2026-11-28T07:30:00Z",
        "schedule_label": "Saturday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_10_k2_savage_mountain",
        "day": 5,
        "slot": "7:30 PM IST",
        "category": "MOUNTAINS & ADVENTURE",
        "question": "Which country is home to K2, the Savage Mountain and second-highest peak on Earth?",
        "clue": "Towering 8,611 meters high in the Karakoram mountain range",
        "options": [
            {"letter": "A", "name": "NEPAL", "code": "np", "correct": False},
            {"letter": "B", "name": "INDIA", "code": "in", "correct": False},
            {"letter": "C", "name": "PAKISTAN", "code": "pk", "correct": True},
            {"letter": "D", "name": "CHINA", "code": "cn", "correct": False},
        ],
        "narration_hook": "Which country is home to K2, the deadliest and second-highest mountain on Earth?",
        "narration_countdown": "Six seconds on the clock. Mountain climbers, make your guess below.",
        "narration_reveal": "Time is up! It's C, Pakistan, home to K2 in the Karakoram range! Subscribe for daily quizzes!",
        "youtube_title": "Which Country Is Home to the Savage Peak K2? 🏔️☠️ #Shorts #Adventure #Quiz",
        "tags": ["shorts", "k2", "pakistan", "mountains", "extreme adventure", "climbing", "daily quiz", "LR Atlas"],
        "voice": "en-US-ChristopherNeural",
        "schedule_time": "2026-11-28T14:00:00Z",
        "schedule_label": "Saturday 7:30 PM IST"
    },

    # DAY 6: Sunday, Nov 29, 2026
    {
        "id": "quiz_10day_11_great_barrier_reef",
        "day": 6,
        "slot": "1:00 PM IST",
        "category": "OCEANS & WONDERS",
        "question": "Which country guards the Great Barrier Reef, the largest living structure on Earth?",
        "clue": "Stretching over 2,300 kilometers and visible from outer space",
        "options": [
            {"letter": "A", "name": "INDONESIA", "code": "id", "correct": False},
            {"letter": "B", "name": "AUSTRALIA", "code": "au", "correct": True},
            {"letter": "C", "name": "BRAZIL", "code": "br", "correct": False},
            {"letter": "D", "name": "UNITED STATES", "code": "us", "correct": False},
        ],
        "narration_hook": "Which country guards the Great Barrier Reef, visible even from outer space?",
        "narration_countdown": "Six seconds to answer. Name this ocean wonderland now.",
        "narration_reveal": "Time is up! It's B, Australia, home to over two thousand kilometers of coral reef! Subscribe for daily trivia!",
        "youtube_title": "Visible From Space: The Largest Living Structure! 🌊🐠 #Shorts #Oceans #Quiz",
        "tags": ["shorts", "australia", "great barrier reef", "ocean facts", "wonders of earth", "daily quiz", "LR Atlas"],
        "voice": "en-US-BrianNeural",
        "schedule_time": "2026-11-29T07:30:00Z",
        "schedule_label": "Sunday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_12_swiss_wealth",
        "day": 6,
        "slot": "7:30 PM IST",
        "category": "WEALTH & BANKING",
        "question": "Which country has 1 in every 10 residents holding millionaire status?",
        "clue": "Renowned for luxury watches, Swiss chocolate, and discreet private banking",
        "options": [
            {"letter": "A", "name": "UNITED ARAB EMIRATES", "code": "ae", "correct": False},
            {"letter": "B", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "C", "name": "SWITZERLAND", "code": "ch", "correct": True},
            {"letter": "D", "name": "GERMANY", "code": "de", "correct": False},
        ],
        "narration_hook": "Which country has one in every ten residents holding millionaire status?",
        "narration_countdown": "Six seconds on the clock. Can you name the wealth capital of Europe?",
        "narration_reveal": "Time is up! It's C, Switzerland, with the highest millionaire density in Europe! Subscribe for daily quizzes!",
        "youtube_title": "Where 1 in 10 People Is a Millionaire! 💰💎 #Shorts #Wealth #Millionaires #Quiz",
        "tags": ["shorts", "switzerland", "millionaires", "wealth", "banking", "finance quiz", "daily quiz", "LR Atlas"],
        "voice": "en-GB-RyanNeural",
        "schedule_time": "2026-11-29T14:00:00Z",
        "schedule_label": "Sunday 7:30 PM IST"
    },

    # DAY 7: Monday, Nov 30, 2026
    {
        "id": "quiz_10day_13_komodo_dragons",
        "day": 7,
        "slot": "1:00 PM IST",
        "category": "WILDLIFE & ISLANDS",
        "question": "Which country is the ONLY place on Earth where wild Komodo Dragons still roam free?",
        "clue": "A tropical paradise made of over 17,000 volcanic islands",
        "options": [
            {"letter": "A", "name": "AUSTRALIA", "code": "au", "correct": False},
            {"letter": "B", "name": "INDONESIA", "code": "id", "correct": True},
            {"letter": "C", "name": "BRAZIL", "code": "br", "correct": False},
            {"letter": "D", "name": "INDIA", "code": "in", "correct": False},
        ],
        "narration_hook": "Which country is the only natural home to the venomous Komodo Dragon?",
        "narration_countdown": "Six seconds to answer. Think tropical islands and drop your guess now.",
        "narration_reveal": "Time is up! It's B, Indonesia, the only home of the giant Komodo Dragon! Subscribe for daily brain trivia!",
        "youtube_title": "The Only Country Where Real Dragons Still Live! 🦎🏝️ #Shorts #Wildlife #Quiz",
        "tags": ["shorts", "komodo dragon", "indonesia", "wildlife quiz", "animals", "islands", "daily quiz", "LR Atlas"],
        "voice": "en-US-GuyNeural",
        "schedule_time": "2026-11-30T07:30:00Z",
        "schedule_label": "Monday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_14_saudi_aramco",
        "day": 7,
        "slot": "7:30 PM IST",
        "category": "ENERGY GIANTS",
        "question": "Which country owns Saudi Aramco, the multi-trillion dollar oil giant?",
        "clue": "Holding the world's most accessible crude oil reserves beneath the desert",
        "options": [
            {"letter": "A", "name": "RUSSIA", "code": "ru", "correct": False},
            {"letter": "B", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "C", "name": "UNITED ARAB EMIRATES", "code": "ae", "correct": False},
            {"letter": "D", "name": "SAUDI ARABIA", "code": "sa", "correct": True},
        ],
        "narration_hook": "Which country is home to Saudi Aramco, the multi-trillion dollar oil superpower?",
        "narration_countdown": "Six seconds on the clock. Can you name this petroleum titan?",
        "narration_reveal": "Time is up! It's D, Saudi Arabia, powering world energy through Aramco! Subscribe for daily quizzes!",
        "youtube_title": "Who Owns the Most Valuable Oil Company on Earth? 🛢️💰 #Shorts #Economy #Quiz",
        "tags": ["shorts", "saudi aramco", "saudi arabia", "oil reserves", "energy", "billionaires", "daily quiz", "LR Atlas"],
        "voice": "en-GB-SoniaNeural",
        "schedule_time": "2026-11-30T14:00:00Z",
        "schedule_label": "Monday 7:30 PM IST"
    },

    # DAY 8: Tuesday, Dec 01, 2026
    {
        "id": "quiz_10day_15_bangladesh_garments",
        "day": 8,
        "slot": "1:00 PM IST",
        "category": "GLOBAL COMMERCE",
        "question": "Which country is the #2 clothing exporter on Earth and home to the Royal Bengal Tiger?",
        "clue": "Supplying clothes to major global brands and home to the Sundarbans mangrove",
        "options": [
            {"letter": "A", "name": "INDIA", "code": "in", "correct": False},
            {"letter": "B", "name": "VIETNAM", "code": "vn", "correct": False},
            {"letter": "C", "name": "BANGLADESH", "code": "bd", "correct": True},
            {"letter": "D", "name": "PAKISTAN", "code": "pk", "correct": False},
        ],
        "narration_hook": "Which country is the world's second-largest clothing exporter and home to the Sundarbans?",
        "narration_countdown": "Six seconds on the clock. Drop your guess in the comments right now.",
        "narration_reveal": "Time is up! It's C, Bangladesh, manufacturing clothes for millions worldwide! Subscribe for daily trivia!",
        "youtube_title": "Who Makes Millions of Your Clothes Every Day? 👕🐅 #Shorts #GlobalTrade #Quiz",
        "tags": ["shorts", "bangladesh", "garments", "fashion trade", "bengal tiger", "daily quiz", "LR Atlas"],
        "voice": "en-US-BrianNeural",
        "schedule_time": "2026-12-01T07:30:00Z",
        "schedule_label": "Tuesday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_16_russia_time_zones",
        "day": 8,
        "slot": "7:30 PM IST",
        "category": "GEOGRAPHY & SCALE",
        "question": "Which country spans across 11 different time zones and covers 1/8th of Earth's land?",
        "clue": "Stretching over 9,000 kilometers from Eastern Europe to the Pacific Ocean",
        "options": [
            {"letter": "A", "name": "CANADA", "code": "ca", "correct": False},
            {"letter": "B", "name": "UNITED STATES", "code": "us", "correct": False},
            {"letter": "C", "name": "CHINA", "code": "cn", "correct": False},
            {"letter": "D", "name": "RUSSIA", "code": "ru", "correct": True},
        ],
        "narration_hook": "Which country spans eleven time zones and covers one-eighth of Earth's landmass?",
        "narration_countdown": "Six seconds on the clock. Can you name the largest country on Earth?",
        "narration_reveal": "Time is up! It's D, Russia, spanning eleven time zones across two continents! Subscribe for daily brain quizzes!",
        "youtube_title": "The Country Spanning 11 Time Zones! 🌍🚂 #Shorts #Geography #Quiz",
        "tags": ["shorts", "russia", "time zones", "largest country", "geography quiz", "earth scale", "daily quiz", "LR Atlas"],
        "voice": "en-US-ChristopherNeural",
        "schedule_time": "2026-12-01T14:00:00Z",
        "schedule_label": "Tuesday 7:30 PM IST"
    },

    # DAY 9: Wednesday, Dec 02, 2026
    {
        "id": "quiz_10day_17_pearl_indian_ocean",
        "day": 9,
        "slot": "1:00 PM IST",
        "category": "ISLANDS & HISTORY",
        "question": "Which teardrop island is known as the Pearl of the Indian Ocean and produces Ceylon tea?",
        "clue": "World-famous for authentic Ceylon cinnamon and ancient fortress Sigiriya",
        "options": [
            {"letter": "A", "name": "INDIA", "code": "in", "correct": False},
            {"letter": "B", "name": "INDONESIA", "code": "id", "correct": False},
            {"letter": "C", "name": "SRI LANKA", "code": "lk", "correct": True},
            {"letter": "D", "name": "NEPAL", "code": "np", "correct": False},
        ],
        "narration_hook": "Which teardrop-shaped island nation is famed as the Pearl of the Indian Ocean?",
        "narration_countdown": "Six seconds to answer. Can you name this tropical paradise?",
        "narration_reveal": "Time is up! It's C, Sri Lanka, the pearl of the Indian Ocean! Subscribe for daily trivia!",
        "youtube_title": "Guess the Pearl of the Indian Ocean in 6 Seconds! 💎🌊 #Shorts #Geography #Quiz",
        "tags": ["shorts", "sri lanka", "ceylon tea", "pearl of indian ocean", "geography trivia", "daily quiz", "LR Atlas"],
        "voice": "en-GB-RyanNeural",
        "schedule_time": "2026-12-02T07:30:00Z",
        "schedule_label": "Wednesday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_18_amazon_rainforest",
        "day": 9,
        "slot": "7:30 PM IST",
        "category": "NATURE & PLANET",
        "question": "Which country contains 60% of the Amazon Rainforest, known as the Lungs of Earth?",
        "clue": "The greatest biodiversity reserve on Earth, spanning millions of square kilometers",
        "options": [
            {"letter": "A", "name": "INDONESIA", "code": "id", "correct": False},
            {"letter": "B", "name": "AUSTRALIA", "code": "au", "correct": False},
            {"letter": "C", "name": "BRAZIL", "code": "br", "correct": True},
            {"letter": "D", "name": "SOUTH AFRICA", "code": "za", "correct": False},
        ],
        "narration_hook": "Which country contains sixty percent of the Amazon rainforest, producing twenty percent of Earth's oxygen?",
        "narration_countdown": "Six seconds on the clock. Make your call in the comments below.",
        "narration_reveal": "Time is up! It's C, Brazil, home to sixty percent of the Amazon basin! Subscribe for daily quizzes!",
        "youtube_title": "Which Country Holds 60% of the Amazon Rainforest? 🌳🦜 #Shorts #Nature #Quiz",
        "tags": ["shorts", "amazon rainforest", "brazil", "nature facts", "lungs of earth", "daily quiz", "LR Atlas"],
        "voice": "en-US-GuyNeural",
        "schedule_time": "2026-12-02T14:00:00Z",
        "schedule_label": "Wednesday 7:30 PM IST"
    },

    # DAY 10: Thursday, Dec 03, 2026
    {
        "id": "quiz_10day_19_new_zealand_sheep",
        "day": 10,
        "slot": "1:00 PM IST",
        "category": "NATURAL WONDERS",
        "question": "Which island nation has 5 times more sheep than people and filmed Lord of the Rings?",
        "clue": "Home to the flightless Kiwi bird and majestic Southern Alps",
        "options": [
            {"letter": "A", "name": "AUSTRALIA", "code": "au", "correct": False},
            {"letter": "B", "name": "NEW ZEALAND", "code": "nz", "correct": True},
            {"letter": "C", "name": "JAPAN", "code": "jp", "correct": False},
            {"letter": "D", "name": "ICELAND", "code": "is", "correct": False},
        ],
        "narration_hook": "Which island country has five times more sheep than people and filmed The Lord of the Rings?",
        "narration_countdown": "Six seconds on the clock. Drop your guess in the comments right now.",
        "narration_reveal": "Time is up! It's B, New Zealand, home to stunning landscapes and the Kiwi! Subscribe for daily trivia!",
        "youtube_title": "More Sheep Than Humans: Guess This Country! 🐑🏔️ #Shorts #NewZealand #Quiz",
        "tags": ["shorts", "new zealand", "lord of the rings", "sheep", "travel trivia", "daily quiz", "LR Atlas"],
        "voice": "en-GB-SoniaNeural",
        "schedule_time": "2026-12-03T07:30:00Z",
        "schedule_label": "Thursday 1:00 PM IST"
    },
    {
        "id": "quiz_10day_20_nobel_prizes",
        "day": 10,
        "slot": "7:30 PM IST",
        "category": "SCIENCE & GENIUS",
        "question": "Which country has won over 400 Nobel Prizes, more than any other nation in history?",
        "clue": "Home to Silicon Valley, NASA, MIT, Harvard, and groundbreaking discoveries",
        "options": [
            {"letter": "A", "name": "UNITED KINGDOM", "code": "gb", "correct": False},
            {"letter": "B", "name": "GERMANY", "code": "de", "correct": False},
            {"letter": "C", "name": "FRANCE", "code": "fr", "correct": False},
            {"letter": "D", "name": "UNITED STATES", "code": "us", "correct": True},
        ],
        "narration_hook": "Which country has won over four hundred Nobel Prizes, more than any other nation in history?",
        "narration_countdown": "Six seconds on the clock. Can you name this scientific powerhouse?",
        "narration_reveal": "Time is up! It's D, the United States, leading the world with over four hundred Nobel laureates! Subscribe for daily brain quizzes!",
        "youtube_title": "Who Has Won the Most Nobel Prizes in History? 🔬🏆 #Shorts #Science #Quiz",
        "tags": ["shorts", "nobel prize", "science quiz", "united states", "genius", "history trivia", "daily quiz", "LR Atlas"],
        "voice": "en-US-BrianNeural",
        "schedule_time": "2026-12-03T14:00:00Z",
        "schedule_label": "Thursday 7:30 PM IST"
    }
]

def get_quiz_by_id(quiz_id):
    for q in QUIZ_TOPICS:
        if q["id"] == quiz_id:
            return q
    return QUIZ_TOPICS[0]

def get_10_day_series():
    return [q for q in QUIZ_TOPICS if q.get("day") is not None]
