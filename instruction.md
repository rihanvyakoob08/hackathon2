# CODEX IMPLEMENTATION INSTRUCTION FILE

Project Name:
KrishiMitra AI

Role:
You are a Principal Solution Architect, Senior Full Stack Engineer, AI Engineer, Product Designer, DevOps Engineer, and Hackathon Mentor.

Your responsibility is to generate a COMPLETE WORKING CODEBASE.

Do NOT generate partial implementations.

Do NOT leave TODO comments.

Do NOT generate placeholders for core functionality.

Generate production-quality MVP code.

---

## PROJECT OVERVIEW

KrishiMitra AI is an Agriculture Intelligence Platform focused on Tamil and Kannada speaking farmers.

The platform combines:

1. AI Assistant
2. Voice Assistant
3. Crop Disease Detection
4. Scheme Eligibility Advisor
5. Grievance Management
6. Agricultural Analytics
7. IVR-Based Farmer Access

Primary Languages:

* Tamil
* Kannada
* English

The solution must run locally.

No Docker required.

---

## TECH STACK

Frontend

* ReactJS
* Vite
* TypeScript
* TailwindCSS
* ShadCN UI
* React Query
* React Router

Backend

* FastAPI
* SQLAlchemy
* Alembic
* Pydantic v2
* JWT Authentication

Database

* SQLite

Storage

/uploads

AI

* OpenAI GPT
* OpenAI Vision
* Sarvam AI STT
* Sarvam AI TTS

Optional

* LangChain only if necessary

---

## DIRECTORY STRUCTURE

backend/

app/

api/
auth/
database/
middleware/
models/
repositories/
schemas/
services/
ai/
utils/

uploads/

main.py

frontend/

src/

components/
pages/
hooks/
layouts/
services/
types/

---

## USER ROLES

1 Farmer

2 Officer

3 Admin

Implement Role Based Access Control.

---

## DATABASE TABLES

users

id
name
email
phone
password_hash
role
language
created_at

roles

id
name

farmer_profiles

id
user_id
district
state
land_size
crop_type

officer_profiles

id
user_id
district

conversations

id
user_id
message
response
intent
created_at

crop_reports

id
user_id
image_path
crop_name

disease_reports

id
user_id
crop_report_id
diagnosis
confidence
treatment
created_at

scheme_checks

id
user_id
scheme_name
eligible
reason
created_at

grievances

id
tracking_id
user_id
category
description
status
assigned_officer_id
created_at

grievance_updates

id
grievance_id
status
remarks
created_at

analytics_events

id
event_type
payload
created_at

---

## AUTHENTICATION

Implement:

POST /api/auth/register

POST /api/auth/login

JWT Access Token

Password hashing using bcrypt.

Role-based route protection.

---

## AI ROUTER

Create IntentRouter service.

Classify user input into:

DISEASE_QUERY

WEATHER_QUERY

SCHEME_QUERY

GRIEVANCE_QUERY

GENERAL_QUERY

Use GPT classification.

Return structured JSON.

---

MODULE 1
CROP ADVISORY AI
----------------

Endpoint:

POST /api/chat

Input

message
language

Workflow

User Message

↓

Intent Router

↓

GPT

↓

Response

Store conversation.

Support Tamil and Kannada.

---

## VOICE ASSISTANT

Endpoints

POST /api/voice/transcribe

POST /api/voice/speak

Transcribe

Audio File

↓

Sarvam STT

↓

Text

Speak

Text

↓

Sarvam TTS

↓

Audio File

Return downloadable audio.

---

## IVR MODULE

Build IVR Adapter Layer.

Directory:

services/ivr/

Create:

ivr_service.py

ivr_router.py

ivr_session_manager.py

ivr_models.py

Implement call flow abstraction.

Flow:

Incoming Call

↓

Language Selection

1 Tamil

2 Kannada

3 English

↓

Voice Capture

↓

Sarvam STT

↓

Intent Router

↓

OpenAI

↓

Sarvam TTS

↓

Audio Response

Mock telephony implementation.

Create adapters:

BaseTelephonyProvider

MockTelephonyProvider

TwilioProvider

ExotelProvider

Only Mock implementation enabled.

Future providers should work without changing business logic.

Endpoints:

POST /api/ivr/incoming

POST /api/ivr/callback

GET /api/ivr/session/{id}

---

MODULE 2
DISEASE DETECTION
-----------------

Endpoint

POST /api/disease/analyze

Input

crop_name
image

Workflow

Upload Image

↓

Store Locally

↓

OpenAI Vision

↓

Disease Detection

↓

Treatment Suggestion

↓

Confidence Score

Store report.

Return JSON.

---

MODULE 3
WEATHER ADVISORY
----------------

Endpoint

POST /api/weather/advice

Input

district
crop

Implement WeatherService.

Create adapter pattern.

WeatherProvider

MockWeatherProvider

Future OpenWeatherProvider

Example Questions

Can I spray pesticide tomorrow?

Should I irrigate today?

Generate GPT recommendation.

---

MODULE 4
SCHEME ELIGIBILITY AI
---------------------

Supported Schemes

PM-KISAN

Krushak Yojana

Mukhyamantri Samathuvapuram

Endpoint

POST /api/scheme/check

Input

state
income
ownership
category

Return

eligible
reason
alternative_schemes

Store history.

---

MODULE 5
GRIEVANCE MANAGEMENT
--------------------

Create grievance.

AI should classify category.

Categories

Subsidy Delay

Crop Loss

Insurance

Irrigation

Market Rate Issue

Endpoint

POST /api/grievance/create

Generate Tracking ID.

Format

KM-2026-XXXXX

Track

GET /api/grievance/{tracking_id}

Officer

PUT /api/officer/grievance/{id}

Statuses

Submitted

Assigned

In Progress

Resolved

---

## OFFICER DASHBOARD

GET /api/officer/dashboard

Metrics

Total Farmers

Total Grievances

Disease Reports

Resolution Rate

Top Disease Trends

District Analytics

Monthly Trends

Generate demo seed data.

---

## ADMIN DASHBOARD

GET /api/admin/users

GET /api/admin/analytics

POST /api/admin/schemes

Capabilities

Manage Users

Manage Officers

Manage Schemes

AI Settings

Analytics

---

## FRONTEND PAGES

Public

/Login
/Register

Farmer

/Dashboard
/Assistant
/Disease
/Schemes
/Grievances
/Profile

Officer

/Officer/Dashboard
/Officer/Grievances
/Officer/Diseases
/Officer/Analytics

Admin

/Admin/Dashboard
/Admin/Users
/Admin/Schemes
/Admin/Analytics

---

## UI REQUIREMENTS

Responsive

Mobile First

Agriculture Theme

Tamil Friendly

Kannada Friendly

Dark Mode Support

Charts

Use Recharts

---

## STATE MANAGEMENT

React Query

Axios Client

JWT Interceptors

Protected Routes

---

## SEED DATA

Generate:

50 Farmers

10 Officers

100 Disease Reports

250 Grievances

Analytics Events

Admin User

Officer User

Farmer User

---

## SWAGGER

All APIs documented.

Use FastAPI OpenAPI.

---

## ENV FILE

Backend

OPENAI_API_KEY=

SARVAM_API_KEY=

JWT_SECRET=

DATABASE_URL=sqlite:///krishimitra.db

UPLOAD_PATH=uploads

---

## README

Generate complete README.

Include:

Architecture

Setup

Run Backend

Run Frontend

Seed Database

Testing

Future Enhancements

---

## DELIVERABLE

Generate the COMPLETE codebase.

Every file must contain code.

No placeholders.

No TODOs.

No pseudocode.

Application must run locally using:

Backend

uvicorn app.main:app --reload

Frontend

npm install
npm run dev

Return all source code files with folder structure.
