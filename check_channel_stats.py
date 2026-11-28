import os
import sys
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

creds = Credentials.from_authorized_user_file("youtube_token.json")
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    with open("youtube_token.json", "w") as f:
        f.write(creds.to_json())

youtube = build("youtube", "v3", credentials=creds)

# 1. Channel stats
channel_resp = youtube.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
channel = channel_resp["items"][0]
title = channel["snippet"]["title"]
stats = channel["statistics"]

print("=" * 70)
print(f"📊 YOUTUBE CHANNEL OVERVIEW: {title}")
print(f"👥 Subscribers: {stats.get('subscriberCount', '0')}")
print(f"👁️ Total Channel Views: {stats.get('viewCount', '0')}")
print(f"🎬 Total Videos: {stats.get('videoCount', '0')}")
print("=" * 70)

# 2. Get uploaded videos
uploads_playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
playlist_items = []
next_page_token = None

while True:
    pl_resp = youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=uploads_playlist_id,
        maxResults=50,
        pageToken=next_page_token
    ).execute()
    playlist_items.extend(pl_resp.get("items", []))
    next_page_token = pl_resp.get("nextPageToken")
    if not next_page_token or len(playlist_items) >= 50:
        break

video_ids = [item["contentDetails"]["videoId"] for item in playlist_items]

# 3. Get video details & stats
video_stats = []
for i in range(0, len(video_ids), 50):
    batch = video_ids[i:i+50]
    v_resp = youtube.videos().list(
        part="snippet,statistics,status",
        id=",".join(batch)
    ).execute()
    for v in v_resp.get("items", []):
        vid_id = v["id"]
        snip = v["snippet"]
        st = v.get("statistics", {})
        status = v.get("status", {})
        video_stats.append({
            "id": vid_id,
            "title": snip["title"],
            "publishedAt": snip.get("publishedAt"),
            "publishAt": status.get("publishAt"),
            "privacyStatus": status.get("privacyStatus"),
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
        })

print("\n" + "=" * 90)
print(f"{'STATUS':<10} | {'VIEWS':<7} | {'LIKES':<5} | {'COMMENTS':<8} | {'RELEASE / SCHEDULE':<20} | {'TITLE'}")
print("-" * 90)

# Sort by publishedAt desc
for v in video_stats:
    privacy = v["privacyStatus"].upper()
    pub = v["publishedAt"] or v["publishAt"] or "N/A"
    pub_short = pub[:16].replace("T", " ") if pub else "N/A"
    title_short = v["title"][:42]
    print(f"{privacy:<10} | {v['views']:<7} | {v['likes']:<5} | {v['comments']:<8} | {pub_short:<20} | {title_short}")
print("=" * 90)

# Summary of recent quiz drops
quiz_videos = [v for v in video_stats if any(q in v["title"].lower() for q in ["quiz", "guess", "country", "who", "which", "90%", "95%"])]
total_quiz_views = sum(v["views"] for v in quiz_videos)
total_quiz_likes = sum(v["likes"] for v in quiz_videos)
total_quiz_comments = sum(v["comments"] for v in quiz_videos)

print(f"\n🧠 QUIZ SERIES SUMMARY:")
print(f"Total Quiz Videos Counted: {len(quiz_videos)}")
print(f"Total Views on Quiz Videos: {total_quiz_views}")
print(f"Total Likes on Quiz Videos: {total_quiz_likes}")
print(f"Total Comments on Quiz Videos: {total_quiz_comments}")
