"""
Automatic Queued Upload & Sync Worker for LR Atlas 10-Day Series.
Reads manifest.json and uploads any rendered drops that haven't been scheduled yet.
Run manually or via daily cron / task scheduler at 1:30 PM IST (when YouTube API quota resets).
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

MANIFEST_PATH = os.path.abspath(r"output\10_day_series\manifest.json")

def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_manifest(manifest):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

def main():
    print("="*65)
    print("🔄 LR ATLAS: SYNCING & UPLOADING QUEUED 10-DAY DROPS")
    print("="*65)

    manifest = load_manifest()
    if not manifest:
        print("No manifest found at", MANIFEST_PATH)
        return

    creds = Credentials.from_authorized_user_file("youtube_token.json")
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("youtube_token.json", "w") as f:
            f.write(creds.to_json())
    youtube = build("youtube", "v3", credentials=creds)

    uploaded_now = 0
    for qid, entry in sorted(manifest.items(), key=lambda x: (x[1].get("day", 99), x[1].get("slot", ""))):
        if entry.get("rendered") and not entry.get("uploaded"):
            mp4_path = entry.get("video_path")
            if not mp4_path or not os.path.exists(mp4_path):
                print(f"⚠️ Video file missing for {qid}: {mp4_path}")
                continue

            quiz = get_quiz_by_id(qid)
            print(f"\n🚀 Uploading [{entry['schedule_label']}]: {quiz['youtube_title']}")
            body = {
                "snippet": {
                    "title": quiz["youtube_title"],
                    "description": (
                        f"{quiz['question']}\n\n"
                        f"💡 Clue: {quiz['clue']}\n\n"
                        "Drop your guess in the comments before time runs out! 👇\n\n"
                        "Subscribe to LR Atlas for daily brain & trivia quizzes! 🔔\n\n"
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
                uploaded_now += 1
                print(f"  ✅ SUCCESS! Scheduled: {vid_url} for {entry['schedule_label']}")
                time.sleep(2)
            except HttpError as err:
                err_str = str(err)
                if "quotaExceeded" in err_str or "uploadLimitExceeded" in err_str:
                    print("\n⚠️ YouTube daily quota reached. Saved state and stopping.")
                    break
                else:
                    print(f"❌ Error uploading {qid}: {err}")
            except Exception as e:
                print(f"❌ Exception uploading {qid}: {e}")

    print("\n" + "="*65)
    print(f"🎉 Session complete! Uploaded {uploaded_now} drops.")
    print("="*65)

if __name__ == "__main__":
    main()
