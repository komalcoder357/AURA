# AURA — Emotion-Aware AI Companion

**An AI/ML portfolio project for emotion-aware conversations, supportive responses, and user-controlled memory.**

AURA is a Flask-based web application designed to explore how text emotion analysis, conversational AI, rule-based decision-making, and safety-oriented response handling can work together in an emotional support assistant.

The project combines a pretrained emotion classification model with a Gemini-powered conversational layer, a rule-based decision engine, user-controlled memory, and a web interface with voice interaction features.

> **Important:** AURA is an experimental support tool, not a medical device, diagnostic system, or replacement for professional mental health care.

## Key Features

- **Text emotion analysis:** Estimates emotions in English using a pretrained Hugging Face model.
- **Conversational AI:** Integrates Google's Gemini API for generating conversational responses.
- **Fallback handling:** Provides a clearly labelled fallback response when AI generation is unavailable.
- **Rule-based decision engine:** Uses message context and application rules to help determine response behaviour.
- **Safety-oriented response handling:** Applies pattern-based rules to identify certain distress-related messages and select appropriate responses.
- **User-controlled memory:** Supports saving information when explicitly requested and retrieving it through keyword overlap.
- **Conversation management:** Includes chat history and search functionality.
- **Authentication:** Registration, login, and user-specific data handling.
- **Personalization:** Profile editing, avatar upload, theme palettes, light/dark modes, and custom colours.
- **Voice interaction:** Browser-based speech recognition and speech synthesis, depending on device and browser support.
- **Webcam preview demo:** Optional camera preview with a face-count feature where the browser supports `FaceDetector`. It does not perform facial emotion recognition.
- **Activity analytics:** Displays available user activity, emotion estimates, response sources, and timing information.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite, SQLAlchemy |
| Emotion classification | Hugging Face Transformers |
| English emotion model | `j-hartmann/emotion-english-distilroberta-base` |
| Conversational AI | Google Gemini API |
| Testing | pytest, jsdom UI checks |
| Configuration | Environment variables |
| Voice interaction | Browser Web Speech APIs |

## Architecture

```text
User
 |
 v
Web Interface
(HTML, CSS, JavaScript)
 |
 v
Flask Application
 |
 +--> Authentication and User Data
 |
 +--> Emotion Analysis
 |      |
 |      +--> English pretrained classifier
 |      +--> Experimental Urdu/Roman Urdu rules
 |
 +--> Rule-Based Decision Engine
 |
 +--> Safety-Oriented Response Handling
 |
 +--> User-Controlled Memory
 |
 +--> Gemini AI Service
 |      |
 |      +--> Generated response
 |      +--> Labelled fallback on failure
 |
 v
Conversation Storage and UI Response
```

The architecture separates emotion analysis, decision logic, safety handling, memory, and conversational generation into modules to make the application easier to test and maintain.

## Emotion Analysis and ML Contribution

AURA uses the pretrained model `j-hartmann/emotion-english-distilroberta-base` to estimate emotions from English text.

The model produces emotion scores that the application can use as signals for its response workflow. These scores are not calibrated probabilities of a person's actual emotional state, and they should not be interpreted as a diagnosis or a measurement of emotional intensity.

For Urdu and Roman Urdu, the current implementation uses experimental keyword-based rules unless a compatible multilingual model is configured.

### Current limitations

- Urdu and Roman Urdu emotion analysis has not been validated on a representative dataset.
- Keyword-based rules can miss context, sarcasm, spelling variations, and mixed-language expressions.
- Negative-emotion trends are heuristic signals, not clinical assessments.
- No facial-expression recognition model is included in the webcam demo.
- The project does not establish that its responses improve mental health outcomes.

## Safety and Responsible Use

AURA includes pattern-based handling for selected direct and indirect distress-related messages.

The safety layer is a software safeguard, not a validated suicide-risk assessment system. It can miss relevant messages or flag harmless ones. It should not be relied upon as the sole source of help during a crisis.

Users should seek appropriate local emergency or professional support when needed. Any deployment involving emotional or sensitive conversations should include careful privacy, security, and safety review.

## Installation

### Requirements

- Python compatible with the versions supported by the project's dependencies
- Git
- Internet access for installing packages, downloading model weights, and using the Gemini API
- A Gemini API key for live AI responses

### 1. Clone the repository

```bash
git clone https://github.com/komalcoder357/AURA.git
cd AURA
```

### 2. Create and activate a virtual environment

**Windows PowerShell:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure the required settings using your own values.

```dotenv
SECRET_KEY=replace_with_a_random_secret
DATABASE_URL=sqlite:///aura.db
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
```

Use a valid model name supported by your Google Gemini API access. The model shown above is an example configuration, not a guarantee of current availability.

Never commit `.env`, API keys, database files, or other secrets to GitHub. Keep `.env.example` free of real credentials.

### 5. Start the application

```bash
python app.py
```

Open:

`http://127.0.0.1:5000`

Camera and microphone features require localhost or HTTPS and browser permission. Voice capabilities vary by browser and device.

## Testing

Run the automated Python test suite:

```bash
python -m pytest -q
```

**Previously recorded result:** 94 tests passed in the local development environment. These tests primarily validate application logic using test doubles and simulated dependencies; they do not prove that every external service works in production.

The project improvement report also records 37 jsdom UI checks. Those checks are not equivalent to full real-browser testing.

### Emotion evaluation

Run the available evaluation script:

```bash
python evaluation/eval_emotion.py
```

Review its output before reporting any scores. Do not claim accuracy, F1, or other performance metrics unless they have actually been measured on a suitable independent dataset.

### Gemini connectivity

The project includes a Gemini connectivity check:

```bash
python check_gemini.py
```

Live API availability depends on the configured key, model access, quotas, and provider status. A successful automated test suite does not guarantee successful live Gemini calls.

## Data Storage and Migration

AURA uses SQLite by default.

The project includes an additive database migration workflow designed to preserve existing user accounts, password hashes, conversations, and memory while introducing new columns. The migration process also creates a database backup before schema changes.

Always keep your own backup before upgrading an existing installation. Test upgrades on a copy of important data before deploying changes.

## Repository Structure

```text
AURA/
├── app.py
├── modules/
│   ├── ai_service.py
│   ├── emotion.py
│   ├── decision_engine.py
│   ├── distress.py
│   ├── safety.py
│   ├── memory.py
│   └── theme.py
├── routes/
│   ├── auth.py
│   ├── chat.py
│   ├── memory.py
│   ├── profile.py
│   └── settings.py
├── templates/
├── static/
│   ├── css/
│   └── js/
├── tests/
├── evaluation/
├── docs/
├── migrations.py
├── requirements.txt
├── .env.example
├── AURA_IMPROVEMENT_REPORT.md
└── README.md
```

This is a high-level overview; consult the repository for the complete current file structure.

## Known Limitations

- English emotion scores are not calibrated and do not estimate emotional intensity.
- Urdu and Roman Urdu support is experimental and lacks representative independent evaluation.
- Safety detection relies on patterns and is not a validated clinical assessment.
- Voice recognition and synthesis depend on browser and device capabilities.
- The webcam demo does not include a facial-expression emotion model.
- Gemini can return temporary errors or become unavailable.
- The application has not been fully validated across real browsers, mobile devices, accessibility tools, and live external services.
- SQLite and the current in-memory login throttling approach have limitations for multi-worker production deployment.
- Sensitive conversational data requires appropriate security, privacy, and retention controls before public deployment.

See [`AURA_IMPROVEMENT_REPORT.md`](AURA_IMPROVEMENT_REPORT.md) and [`docs/limitations.md`](docs/limitations.md) for additional implementation details and verification status.

## Future Work

- Evaluate emotion classification using a documented, independent test dataset.
- Investigate multilingual emotion models for Urdu and Roman Urdu.
- Measure model performance using suitable metrics, including per-class precision, recall, and F1.
- Evaluate emotion-aware response quality with a clearly defined protocol.
- Improve safety coverage and assess false positives and false negatives.
- Conduct real-browser, mobile, accessibility, and privacy testing.
- Explore a separately evaluated facial-expression module as a future extension.
- Improve deployment configuration, monitoring, and database support.

## Project Goals

AURA is intended as a learning and portfolio project demonstrating the integration of pretrained NLP models, backend engineering, conversational AI, rule-based logic, testing, and responsible-use considerations.

Its purpose is to provide a foundation for further experimentation and evaluation—not to claim clinically validated emotion understanding.

## License

Check the repository for a license file before reusing, modifying, or distributing this project. If no license is present, do not assume that the code is open for unrestricted reuse.
## 📸 AURA — Application Screenshots

This gallery showcases the AURA application's interface, emotion analysis, AI interaction, settings, and other available features.

### Application Overview

![AURA Screenshot 1](pictures/Screenshot%20%281%29.png)
![AURA Screenshot 2](pictures/Screenshot%20%282%29.png)
![AURA Screenshot 3](pictures/Screenshot%20%283%29.png)
![AURA Screenshot 4](pictures/Screenshot%20%284%29.png)
![AURA Screenshot 5](pictures/Screenshot%20%285%29.png)
![AURA Screenshot 6](pictures/Screenshot%20%286%29.png)
![AURA Screenshot 7](pictures/Screenshot%20%287%29.png)
![AURA Screenshot 8](pictures/Screenshot%20%288%29.png)
![AURA Screenshot 9](pictures/Screenshot%20%289%29.png)
![AURA Screenshot 10](pictures/Screenshot%20%2810%29.png)
![AURA Screenshot 11](pictures/Screenshot%20%2811%29.png)
![AURA Screenshot 12](pictures/Screenshot%20%2812%29.png)
![AURA Screenshot 13](pictures/Screenshot%20%2813%29.png)
![AURA Screenshot 14](pictures/Screenshot%20%2814%29.png)
![AURA Screenshot 15](pictures/Screenshot%20%2815%29.png)
![AURA Screenshot 16](pictures/Screenshot%20%2816%29.png)
![AURA Screenshot 17](pictures/Screenshot%20%2817%29.png)
![AURA Screenshot 18](pictures/Screenshot%20%2818%29.png)
![AURA Screenshot 19](pictures/Screenshot%20%2819%29.png)
![AURA Screenshot 20](pictures/Screenshot%20%2820%29.png)
![AURA Screenshot 21](pictures/Screenshot%20%2821%29.png)
![AURA Screenshot 22](pictures/Screenshot%20%2822%29.png)
![AURA Screenshot 23](pictures/Screenshot%20%2823%29.png)
![AURA Screenshot 24](pictures/Screenshot%20%2824%29.png)
![AURA Screenshot 25](pictures/Screenshot%20%2825%29.png)