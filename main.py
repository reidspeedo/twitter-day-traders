import tweepy
import logging.config
import os
import time
import threading
from datetime import datetime
from datetime import timedelta

from services import services as svr
from configuration import logger
# https://twitter.com/anyuser/status/1371863979547590668

def create_api():
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        # logger.info("authentication success")
    except Exception as e:
        # logger.error("Error creating API", exc_info=True)
        raise e
    # logger.info("API created")
    return api
class FavRetweetListener(tweepy.StreamListener):
    def __init__(self, api):
        self.api = api
        self.me = api.me()

    def on_status(self, tweet):
        clean_tweet, include_tweet, tickers = self.filter_extract_tickers(tweet)
        if include_tweet:
            new_row = self.format_tweet(tweet, tickers)
            svr.create_tweet(new_row)

    def on_error(self, status):
        logger.error(status)

    def filter_extract_tickers(self, tweet):
        unique_tickers = []
        if '$' in tweet.text:
            split_tweet = tweet.text.split()
            tickers = split_tweet.copy()
            for word in split_tweet:
                if '$' not in word:
                    tickers.remove(word)
                elif any(char.isdigit() for char in word):
                    tickers.remove(word)
                elif not any(char.isalpha() for char in word):
                    tickers.remove(word)
                else:
                    pass

            for i in tickers:
                tick = i.upper().replace('.','')
                if tick not in unique_tickers:
                    unique_tickers.append(tick.upper())

            if len(unique_tickers) > 0:
                include_tweet = True
            else:
                include_tweet = False
        else:
            logging.info(f'No ticker found in tweet: {tweet.id}')
            include_tweet = False
        return tweet, include_tweet, unique_tickers

    def format_tweet(self, tweet, tickers):
        df_new_row = \
            {
                'tweet_id': tweet.id_str,
                'create_at': tweet.created_at,
                'user_id': tweet.user.id_str,
                'user_name': tweet.user.screen_name,
                'tweet_text': tweet.text,
                'tickers': tickers
            }
        # logger.info(df_new_row)
        return df_new_row
def streamer(my_twitterid = '1369887486810353664'):
    api = create_api()
    friends = [my_twitterid]
    for follower in api.friends():
        friends.append(str(follower.id))
    tweets_listener = FavRetweetListener(api)
    stream = tweepy.Stream(api.auth, tweets_listener)
    stream.filter(follow=friends)
    return api

class GraphTickers():
    def __init__(self):
        self.last_datetime = ''
        self.graph_data = {}
        self.refresh_graph_data()

    def refresh_graph_data(self):
        while True:
            if self.last_datetime == '':
                # self.last_datetime = datetime.today()
                self.last_datetime = datetime(2021, 3, 16, 0, 0, 0)

            self.last_datetime, delta_graph_data = svr.retrieve_tweets(self.last_datetime, self.last_datetime)
            self.add_delta_to_graph(delta_graph_data)
            logger.info(self.last_datetime)

            sort_graph_data = {k: v for k, v in sorted(self.graph_data.items(), key=lambda item: item[1], reverse=True)}
            logger.info('\n\n\n\n Live Chart Updates: \n' + str(sort_graph_data))
            time.sleep(10)

    def add_delta_to_graph(self, delta_graph_data):
        for key, value in delta_graph_data.items():
            if key in self.graph_data.keys():
                self.graph_data[key] += value
            else:
                self.graph_data[key] = value



def grapher_function():
    grapher = GraphTickers()
    return grapher

if __name__ == '__main__':
    graphing_object = threading.Thread(target=grapher_function)
    stream_object = threading.Thread(target=streamer)
    stream_object.start()
    graphing_object.start()








