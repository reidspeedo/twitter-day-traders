import tweepy
import logging.config
import os
import time
import threading
import datetime
import alpaca_trade_api as tradeapi
from sys import platform
from math import floor

from services import services as svr
from configuration import logger

if platform == 'darwin':
    import caffeine
    caffeine.on(display=False)

# https://twitter.com/anyuser/status/1372422808941125632

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

def create_alpaca_api():
    alpaca_api_key = 'PKF4UWKK8V961RO3AFDC'
    alpaca_api_secret = 'lKuIbsEsP5oKdJAMXpbqgr4dHXeryLs5h00Uquur'
    alpaca_base_url = 'https://paper-api.alpaca.markets'
    alpaca_api = tradeapi.REST(alpaca_api_key, alpaca_api_secret, alpaca_base_url, api_version='v2')
    return alpaca_api

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
                'create_at': tweet.created_at - datetime.timedelta(hours=7),
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

    while True:
        try:
            stream = tweepy.Stream(api.auth, tweets_listener)
            stream.filter(follow=friends)
        except:
            continue
    return api

class GraphTickers():
    def __init__(self):
        self.kill_all = False
        self.last_datetime = ''
        self.graph_data = {}
        self.watchlist_dict = {}
        self.current_positions = {}
        self.orders = []
        self.cannot_buy = {'$QQQ':(), '$SPY':()}
        self.buy_orders = {}
        self.sell_orders = {}
        self.cannot_sell = {}
        self.total_percentage = 0

    def percentage_change(self,original, current):
        diff = ((current - original) / original) * 100
        return round(diff,2)
    def logging_function(self, refresh=5, end_hour=13, end_minute=0):
        while True:
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                logger.info(f'----------------sleeping until trading opens-----------------')
                break
            if self.kill_all:
                logging.info(f'----------------all processes killed-----------------')
                break
            else:
                cp_string = ''
                total_percentage = 0
                logger.info('\n-------------------------------------------------------------')
                logger.info(f'Ticker Watchlist: {self.watchlist_dict}')
                for key, value in self.current_positions.items():
                    percentage = self.percentage_change(float(value['avg_entry_price']), float(value['current_price']))
                    total_percentage = total_percentage + percentage
                    cp_string = cp_string + f" {key}: {percentage}%"

                logger.info(f'Current Positions: {round(total_percentage,2)}% / {cp_string}')
                logger.info(f'Orders Pending: {self.orders}')
                logger.info(f'Successfully initiated BUY for: {self.buy_orders}')
                logger.info(f'Successfully initiated SELL for: {self.sell_orders}')
                logger.info(f'Error selling for: {self.cannot_sell}')
                logger.info(f'Error buying for: {self.cannot_buy}')
                logger.info('-------------------------------------------------------------')
            time.sleep(refresh)
    def refresh_graph_data(self, start_date=datetime.datetime.today().date(), refresh=5, end_hour=13, end_minute=0):
        while True:
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                break
            if self.kill_all:
                logging.info(f'----------------all processes killed-----------------')
                break
            if self.last_datetime == '':
                self.last_datetime = datetime.datetime.combine(start_date, datetime.time(0, 0))

            self.last_datetime, delta_graph_data = svr.retrieve_tweets(self.last_datetime, self.last_datetime)
            for key, value in delta_graph_data.items():
                if key in self.graph_data.keys():
                    self.graph_data[key] += value
                else:
                    self.graph_data[key] = value
            time.sleep(refresh)
    def watchlist(self, refresh=5, count=10, end_hour=13, end_minute=0):
        while True:
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                break
            if self.kill_all:
                logging.info(f'----------------all processes killed-----------------')
                break
            self.watchlist_dict = {}
            for i, (k, v) in enumerate(sorted(self.graph_data.items(), key=lambda item: item[1], reverse=True)):
                if len(self.watchlist_dict) < (count) and (k not in self.cannot_buy.keys()):
                    self.watchlist_dict[k] = v
            time.sleep(refresh)
    def alpca_buy_ticker(self, alpaca_api, refresh=5, end_hour=13, end_minute=0):
        available_cash = float(alpaca_api.get_account().cash)
        cash_for_each_stock = available_cash/10
        time.sleep(10)
        while True:
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                break
            if self.kill_all:
                logging.info(f'----------------all processes killed-----------------')
                break

            for ticker in self.watchlist_dict.keys():
                if ticker not in self.current_positions.keys() and ticker not in self.orders:
                    available_cash = float(alpaca_api.get_account().cash)
                    if available_cash > cash_for_each_stock:
                        try:
                            jtick = ticker.replace('$', '')
                            ticker_ask_price = alpaca_api.get_barset(jtick, '1Min', limit=1)[jtick][0].h
                            qty = floor(cash_for_each_stock / ticker_ask_price)
                            alpaca_api.submit_order(symbol=jtick, qty=qty, side='buy', type='market', time_in_force='day')
                            self.buy_orders[ticker] = datetime.datetime.now()
                        except Exception as e:
                            self.cannot_buy[ticker] = (e, datetime.datetime.now())
                    else:
                        pass

            time.sleep(refresh)
    def alpaca_monitor_and_sell(self, alpaca_api, refresh = 5, max_diff = 10, diff = 2, end_hour=13, end_minute=0):
        while True:
            temp_current_position = {}
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                break
            if self.kill_all:
                logging.info(f'----------------all processes killed-----------------')
                break

            all_position_details = alpaca_api.list_positions()
            all_order_details = alpaca_api.list_orders()
            total_percentage = 0
            for position in all_position_details:
                ticker = f'${position.symbol}'
                temp_dict = dict(current_price=position.current_price,avg_entry_price=position.avg_entry_price,qty=position.qty)
                temp_current_position[ticker] = temp_dict
                self.current_positions = temp_current_position
                percentage = self.percentage_change(float(position.avg_entry_price), float(position.current_price))
                total_percentage = total_percentage + percentage

            self.total_percentage = total_percentage

            if total_percentage < -10 or total_percentage > 10:
                all_position_details = alpaca_api.list_positions()
                for position in all_position_details:
                    alpaca_api.submit_order(symbol=position.symbol, qty=position.qty, side='sell', type='market', time_in_force='day')
                self.kill_all = True

            self.orders = [f'${order.symbol}' for order in all_order_details]
            time.sleep(refresh)

def main(start_hour=6, start_minute=35, wait_start=14400, end_hour=13, end_minute=0):
    alpaca_api = create_alpaca_api()
    grapher = GraphTickers()
    stream_object = threading.Thread(target=streamer)
    stream_object.start()

    for i in range(0, 365):
        t = datetime.datetime.today()
        future = datetime.datetime(t.year, t.month, t.day, start_hour, start_minute)
        if t.hour > start_hour:
            future += datetime.timedelta(days=1)
        elif t.hour == start_hour and t.minute > start_minute:
            future += datetime.timedelta(days=1)
        else:
            pass
        wait = (future - t).total_seconds()
        logging.info(f'...Paused for {wait/60} minutes until next runtime...')
        time.sleep(wait)
        grapher.kill_all = False

        logging_function_object = threading.Thread(target=grapher.logging_function, kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        watchlist_object = threading.Thread(target=grapher.watchlist, kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        graphing_object = threading.Thread(target=grapher.refresh_graph_data, kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        alpaca_object = threading.Thread(target=grapher.alpaca_monitor_and_sell, args=(alpaca_api,), kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        alpaca_buy = threading.Thread(target=grapher.alpca_buy_ticker, args=(alpaca_api,), kwargs={'end_hour':end_hour, 'end_minute':end_minute})

        logging_function_object.start()
        watchlist_object.start()
        graphing_object.start()

        time.sleep(wait_start)
        alpaca_object.start()
        alpaca_buy.start()

        logging_function_object.join()
        watchlist_object.join()
        graphing_object.join()
        alpaca_object.join()
        alpaca_buy.join()

if __name__ == '__main__':
    main(start_hour=6, start_minute=45, wait_start=.1, end_hour=12, end_minute=55)
    # alpaca_api = create_alpaca_api()
    # wkey = alpaca_api.get_barset('UPST','1Min', limit=5)
    # for bar in wkey['UPST']:
    #     print(bar)


    # current_moment = datetime.datetime.now()
    # start_hour = int(current_moment.strftime('%-H'))
    # start_minute = int(current_moment.strftime('%-M'))+1
    # main(start_hour=start_hour, start_minute=start_minute, wait_start=6000, end_hour=10, end_minute=55)




# Add string datetime
# Convert to datetime
# Import Twilio
# Stop Limit
# Add extended watchlist
# Combine classes?




class FavRetweetListener(tweepy.StreamListener):
    def __init__(self, twitter_api):
        self.twitter_api = twitter_api
        self.me = twitter_api.me()

    def on_status(self, tweet):
        clean_tweet, include_tweet, tickers = self.filter_extract_tickers(tweet)
        if include_tweet:
               db_tweet = self.format_tweet(tweet, tickers)
               svr.create_tweet(db_tweet)

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
                tick = sub("[^0-9a-zA-Z]+", i).upper()
                # tick = i.upper()

                if tick not in unique_tickers:
                    unique_tickers.append(tick.upper())

            if len(unique_tickers) > 0:
                include_tweet = True
            else:
                include_tweet = False
        else:
            logging.info(f'Pass -> No ticker found in tweet: {tweet.id}')
            include_tweet = False
        return tweet, include_tweet, unique_tickers

    def format_tweet(self, tweet, tickers):
        db_tweet = \
            {
                'tweet_id': tweet.id_str,
                'create_at': tweet.created_at - datetime.timedelta(hours=7), #PST Time
                'user_id': tweet.user.id_str,
                'user_name': tweet.user.screen_name,
                'tweet_text': tweet.text,
                'tickers': tickers
            }
        return db_tweet



