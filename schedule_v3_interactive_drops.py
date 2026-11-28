"""
Upload and schedule the pre-rendered V3 interactive quiz drops on YouTube.
Reads output/v3_interactive_series/manifest_v3.json and schedules each drop according to its schedule_time.
"""

import os
import sys
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from quiz_database import get_quiz_by_id

MANIFEST_PATH = os.path.abspath(r"output\v3_interactive_series\manifest_v3.json")

def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_manifest(manifest):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

def main():
    print("=" * 70)
    print("🚀 SCHEDULING V3 INTERACTIVE DROPS ON YOUTUBE")
    print("=" * 70)

    manifest = load_manifest()
    if not manifest:
        print("❌ No manifest found at", MANIFEST_PATH)
        return

    try:
        creds = Credentials.from_authorized_user_file("youtube_token.json")
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open("youtube_token.json", "w") as f:
                f.write(creds.to_json())
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print("Please run 'python reauth_youtube.py' first to refresh your YouTube token.")
        return

    uploaded = 0
    for qid, entry in sorted(manifest.items(), key=lambda x: (x[1].get("day", 99), x[1].get("slot", ""))):
        if entry.get("rendered") and not entry.get("uploaded"):
            mp4_path = entry.get("video_path")
            if not mp4_path or not os.path.exists(mp4_path):
                print(f"⚠️ Video file missing for {qid}")
                continue

            quiz = get_quiz_by_id(qid)
            print(f"\n🚀 Uploading [{entry['schedule_label']}]: {quiz['youtube_title']}")
            
            body = {
                "snippet": {
                    "title": quiz["youtube_title"],
                    "description": (
                        f"{quiz['question']}\n\n"
                        f"💡 Clue: {quiz['clue']}\n\n"
                        f"🧠 {quiz.get('difficulty', 'Trivia Quiz')}\n\n"
                        "Can you guess it in 6 seconds? Drop your answer below! 👇\n\n"
                        "Subscribe to LR Atlas for daily high-IQ brain quizzes! 🔔\n\n"
                        + " ".join(f"#{t.replace(' ', '')}" for t in quiz["tags"])
                    ),
                    "tags": quiz["tags"],
                    "categoryId": "27",
                },
                "status": {
                    "privacyStatus": "private",
                    "publishAt": quiz["schedule_time"],
                    "selfDeclaredMadeForKids": False,
                    "madeForKids": False,
                },
            }

            try:
                media = MediaFileUpload(mp4_path, mimetype="video/mp4", resumable=True)
                req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
                resp = None
                while resp is None:
                    st, resp = req.next_chunk()
                    if st:
                        print(f"  Uploading... {int(st.progress() * 100)}%")

                vid_id = resp["id"]
                vid_url = f"https://youtube.com/shorts/{vid_id}"
                entry["uploaded"] = True
                entry["video_id"] = vid_id
                entry["url"] = vid_url
                manifest[qid] = entry
                save_manifest(manifest)
                uploaded += 1
                print(f"  ✅ SUCCESS! Scheduled: {vid_url} for {entry['schedule_label']}")
                time.sleep(2)
            except HttpError as err:
                err_str = str(err)
                if "quotaExceeded" in err_str or "uploadLimitExceeded" in err_str:
                    print("\n⚠️ YouTube daily quota reached. Stopping.")
                    break
                else:
                    print(f"❌ Upload error on {qid}: {err}")
            except Exception as e:
                print(f"❌ Exception on {qid}: {e}")

    print("\n" + "=" * 70)
    print(f"🎉 Batch upload completed! Scheduled {uploaded} drops.")
    print("=" * 70)

if __name__ == "__main__":
    main()
