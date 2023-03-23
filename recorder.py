#!/usr/bin/env python3.9

import os
import json
import sqlite3
from utils import sns_timestamp_to_utc_datetime

import snscrape.modules.twitter as sntwitter


class Recorder:
    def __init__(self, query):
        self._query = query
        self._create_db()

    def _create_table(self, create_table_sql):
        try:
            self._cursor.execute(create_table_sql)
        except Exception as e:
            print(e)

    def _create_db(self):
        path = "db/record.db"
        scriptdir = os.path.dirname(__file__)
        db_path = os.path.join(scriptdir, path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._cursor = self.conn.cursor()

        create_queries_table_sql = """
        CREATE TABLE IF NOT EXISTS queries
        (query text, latest_result_date text)
        """

        create_users_table_sql = """
        CREATE TABLE IF NOT EXISTS users
        (user_id int PRIMARY KEY, screen_name text, created_at text, following_count integer, followers_count integer, tweet_count integer, favourites_count integer, media_count integer, last_seen_post_id integer, suspended boolean)
        WITHOUT ROWID
        """

        create_posts_table_sql = """
        CREATE TABLE IF NOT EXISTS posts
        (post_id int PRIMARY KEY, account_id integer, created_at text, source text, reply_count integer, retweet_count integer, like_count integer, quote_count integer, view_count integer, query text, content text)
        WITHOUT ROWID
        """

        self._create_table(create_queries_table_sql)
        self._create_table(create_users_table_sql)
        self._create_table(create_posts_table_sql)

    def search_and_record(self):
        results = sntwitter.TwitterSearchScraper(self._query)
        self.record(results)

    def record(self, results):
        """
        Collect results incrementally
        """
        self._cursor.execute("SELECT rowid, latest_result_date from queries WHERE query = (?)", (self._query,))
        self.conn.commit()

        query_record = self._cursor.fetchall()

        # if the query is not new, get the timestamp for the latest post previously seen
        if len(query_record) != 0:
            latest_result_date = query_record[0][1]
        else:
            latest_result_date = "1970-01-01T00:00:00+00:00"
            self._cursor.execute("INSERT INTO queries VALUES (?,?)", (self._query, "1970-01-01T00:00:00+00:00"))

        recorded_latest_timestamp = sns_timestamp_to_utc_datetime(latest_result_date)

        count = 0
        for result in results.get_items():
            content = json.loads(result.json())
            # print(content)

            user_id = int(content["user"]["id"])
            screen_name = content["user"]["username"]
            created_at = content["user"]["created"]
            following_count = int(content["user"]["friendsCount"])
            followers_count = int(content["user"]["followersCount"])
            tweet_count = int(content["user"]["statusesCount"])
            favourites_count = int(content["user"]["favouritesCount"])
            media_count = int(content["user"]["mediaCount"])

            # tweet information
            text_raw = content["rawContent"]
            post_id = int(content["id"])
            posted_at = content["date"]
            source = content["source"]

            if content["sourceLabel"] != "Twitter Web App":
                print(f"{source:.>100}")

            timestamp = sns_timestamp_to_utc_datetime(posted_at)
            # if latest post in the current search
            if count == 0:
                # update the table if unseen
                if timestamp > recorded_latest_timestamp:
                    print("new data seen!")
                    self._cursor.execute(
                        "UPDATE queries SET latest_result_date=? WHERE query=?", (posted_at, self._query)
                    )

            # compare the current timestamp with the recorded latest timestamp
            if timestamp <= recorded_latest_timestamp:
                print(f"counter: {count}, reaches the point of last search")
                break

            print(f"counter: {count:<6} timestamp: {posted_at:<25} user:{screen_name:<16} text: {text_raw}")

            # tweet statistics
            if content["viewCount"] is not None:
                view_count = int(content["viewCount"])
            else:
                view_count = None
            reply_count = int(content["replyCount"])
            retweet_count = int(content["retweetCount"])
            like_count = int(content["likeCount"])
            quote_count = int(content["quoteCount"])

            # related entities
            # retweeted_tweet = content["retweetedTweet"]
            # quoted_tweet = content["quotedTweet"]
            # in_reply_to_tweet_id = content["inReplyToTweetId"]
            # in_reply_to_user = content["inReplyToUser"]
            self._cursor.execute(
                "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    user_id,
                    screen_name,
                    created_at,
                    following_count,
                    followers_count,
                    tweet_count,
                    favourites_count,
                    media_count,
                    post_id,
                    False,
                ),
            )
            
            self._cursor.execute(
                "UPDATE posts SET reply_count=?, retweet_count=?, like_count=?, quote_count=?, view_count=? WHERE post_id=?", (reply_count, retweet_count, like_count, quote_count, view_count, post_id)
            )
            self._cursor.execute(
                "INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    post_id,
                    user_id,
                    posted_at,
                    source,
                    reply_count,
                    retweet_count,
                    like_count,
                    quote_count,
                    view_count,
                    self._query,
                    text_raw,
                ),
            )
            self.conn.commit()

            count += 1
            

    def check(self):
        q = self._cursor.execute("SELECT * from queries")
        for x in self._cursor.fetchall():
            print(dict(x))

        q = self._cursor.execute("SELECT * from users")
        for x in self._cursor.fetchall():
            print(dict(x))

        # q = self._cursor.execute("SELECT * FROM posts")
        # q = self._cursor.execute("SELECT * FROM posts WHERE created_at BETWEEN '2023-01-01' AND '2023-03-01'")
        q = self._cursor.execute("SELECT * FROM posts WHERE source NOT LIKE '%Twitter Web App%'")
        for x in self._cursor.fetchall():
            print(dict(x))