# Writtique

Writtique is a blogging platform built with Flask and SQLite. Users sign up, write posts with optional images and videos, comment on each other's posts, subscribe to authors, and earn badges for posting.

## Features

- Signup and login. Passwords are stored as hashes, not plain text.
- Write a post with a title, content and genre, and attach an image or a video if you want.
- Home feed with a search box (matches title and content) and a genre filter.
- Comments on any post.
- Subscribe and unsubscribe to other authors, with a page that lists everyone you follow.
- Leaderboard that ranks users by number of posts.
- Profile page that shows your own posts and your badges. The badges are First Post, 10 Posts and Multimedia Post (a post with an image or video).
- Daily login streak, which goes up by one for each day in a row that you log in and resets if you miss a day.
- Authors can delete their own posts.

## Tech stack

Python, Flask, SQLite, HTML, CSS and JavaScript, with Jinja templates.

## Project structure

```
app.py              Flask app: routes, database setup, badges and streaks
templates/          HTML pages (login, signup, home, write, profile, and so on)
static/uploads/     Images and videos uploaded with posts (created on first run)
users.db            SQLite database (created on first run)
```

## How to run it

1. Install Python 3 if you don't have it.
2. Install Flask:

   ```
   pip install flask
   ```

3. From the project folder, start the app:

   ```
   python app.py
   ```

4. Open http://127.0.0.1:5000 in your browser. You will land on the login page, so sign up first.

The database tables and the uploads folder are created automatically the first time the app starts.

## Database

The app uses five SQLite tables: `users`, `posts`, `comments`, `subscriptions` and `user_streaks`.

## Notes

- The secret key in `app.py` is a placeholder. Change it before deploying the app anywhere public.
- The app runs with `debug=True`, which is fine for local use but should be turned off in a real deployment.
