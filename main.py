import tweepy
import logging.config
import os
import time
import threading
import datetime
import alpaca_trade_api as tradeapi
from re import sub
from sys import platform
from math import floor

from services import services as svr
from configuration import logger

if platform == 'darwin':
    import caffeine

    caffeine.on(display=False)


# https://twitter.com/anyuser/status/1372980941375741954

def create_twitter_api():
    # Twitter
    twitter_consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    twitter_consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
    twitter_access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    twitter_access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    twitter_auth = tweepy.OAuthHandler(twitter_consumer_key, twitter_consumer_secret)
    twitter_auth.set_access_token(twitter_access_token, twitter_access_token_secret)
    twitter_api = tweepy.API(twitter_auth)

    try:
        twitter_api.verify_credentials()
        logger.error("tweepy authentication success")
    except Exception as e:
        logger.error("Error creating API", exc_info=True)
        raise e
    return twitter_api

class FavRetweetListener(tweepy.StreamListener):
    def __init__(self, twitter_api):
        self.api = twitter_api
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
                tick = sub("[^a-zA-Z]", '', i).upper()

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

def tweet_streamer(my_twitterid='1369887486810353664'):
    twitter_api = create_twitter_api()
    friends = [my_twitterid]
    for follower in twitter_api.friends():
        friends.append(str(follower.id))
    tweets_listener = FavRetweetListener(twitter_api)

    while True:
        try:
            stream = tweepy.Stream(twitter_api.auth, tweets_listener)
            stream.filter(follow=friends)
        except Exception as e:
            logger.error(e)
            continue
    return twitter_api

def create_alpaca_api():
    alpaca_api_key = 'PK7QWK1610PEO36RLK4V'
    alpaca_api_secret = 'bQ12bzbcCt7T2gQq6UuZQ8bkUljl2U8VdV8PC9hP'
    alpaca_base_url = 'https://paper-api.alpaca.markets'
    alpaca_api = tradeapi.REST(alpaca_api_key, alpaca_api_secret, alpaca_base_url, api_version='v2')
    return alpaca_api

class Stock_Trader():
    def __init__(self, alpaca_api):

        self.alpaca_api = alpaca_api

        # Kill Functions
        self.kill_console_logger = False
        self.kill_stock_mentions = False
        self.kill_alpaca_monitor = False
        self.kill_alpaca_buy = False
        self.kill_alpaca_sell = False

        self.last_datetime = ''
        self.stock_mention_counter = {}
        self.watchlist_dict = {}

        self.current_positions = {}
        self.orders = []
        self.total_percentage = 0

        self.cannot_sell = {}
        self.cannot_buy = {'$QQQ': (), '$SPY': ()}
        self.buy_orders = {}
        self.sell_orders = {}


        # For Alpaca functions
        self.starting_available_cash = float(alpaca_api.get_account().cash)
        self.cash_for_each_stock = self.starting_available_cash / 10

    def percentage_change(self, original, current):
        diff = ((current - original) / original) * 100
        return round(diff, 2)

    def kill_all(self):
        self.kill_console_logger = True
        self.kill_stock_mentions = True
        self.kill_alpaca_monitor = True
        self.kill_alpaca_buy = True
        self.kill_alpaca_sell = True

    def wait_until(self, stock_trader_function, start_hour, start_minute):
        t = datetime.datetime.today()
        future = datetime.datetime(t.year, t.month, t.day, start_hour, start_minute)
        if t.hour > start_hour:
            future += datetime.timedelta(days=1)
        elif t.hour == start_hour and t.minute > start_minute:
            future += datetime.timedelta(days=1)
        else:
            pass
        wait = (future - t).total_seconds()
        logger.info(
            f'----- Function: {stock_trader_function.__name__} paused for {wait / 60} minutes until next runtime -----')
        time.sleep(wait)

    def thread_decorator(self, stock_trader_function, kill_switch, start_time, end_time, refresh):
        start_hour = int(start_time.split(":")[0].lstrip("0"))
        start_minute = int(start_time.split(":")[1].lstrip("0"))
        end_hour = int(end_time.split(":")[0].lstrip("0"))
        end_minute = int(end_time.split(":")[1].lstrip("0"))
        self.wait_until(stock_trader_function, start_hour, start_minute)
        while True:
            current_hour = datetime.datetime.today().hour
            current_minute = datetime.datetime.today().minute
            if current_hour >= end_hour and current_minute >= end_minute:
                logger.info(f'----- End time reached for {stock_trader_function.__name__} process.')
                break
            elif kill_switch:
                logger.info(f'----- Process {stock_trader_function.__name__} has been terminated.')
            stock_trader_function()
            time.sleep(refresh)

    def console_logger(self):
        cp_string = ''
        total_percentage = 0

        for key, value in self.current_positions.items():
            percentage = self.percentage_change(float(value['avg_entry_price']), float(value['current_price']))
            total_percentage = total_percentage + percentage
            cp_string = cp_string + f" {key}: {percentage}%"

        logger.info('\n-------------------------------------------------------------')
        logger.info(f'Ticker Watchlist: {self.watchlist_dict}')
        logger.info(f'Current Positions: {round(total_percentage, 2)}% / {cp_string}')
        logger.info(f'Orders Pending: {self.orders}')
        logger.info(f'Successfully initiated BUY for: {self.buy_orders}')
        logger.info(f'Successfully initiated SELL for: {self.sell_orders}')
        logger.info(f'Error selling for: {self.cannot_sell}')
        logger.info(f'Error buying for: {self.cannot_buy}')
        logger.info('-------------------------------------------------------------')

    def stock_mentions(self, count=10):
        if self.last_datetime == '':
            midnight = datetime.datetime.today().replace(hour=0, minute=0)
            self.last_datetime = midnight

        self.last_datetime, delta_graph_data = svr.retrieve_tweets(self.last_datetime, self.last_datetime)
        for key, value in delta_graph_data.items():
            if key in self.stock_mention_counter.keys():
                self.stock_mention_counter[key] += value
            else:
                self.stock_mention_counter[key] = value

        self.watchlist_dict = {}
        for i, (k, v) in enumerate(sorted(self.stock_mention_counter.items(), key=lambda item: item[1], reverse=True)):
            if len(self.watchlist_dict) < (count) and (k not in self.cannot_buy.keys()):
                self.watchlist_dict[k] = v

    def alpca_buy_ticker(self):
        time.sleep(10)
        for ticker in self.watchlist_dict.keys():
            if ticker not in self.current_positions.keys() and ticker not in self.orders:
                available_cash = float(self.alpaca_api.get_account().cash)
                if available_cash > self.cash_for_each_stock:
                    try:
                        ticker_ask_price = self.alpaca_api.get_barset(ticker, '1Min', limit=1)[ticker][0].h
                        qty = floor(self.cash_for_each_stock / ticker_ask_price)
                        self.alpaca_api.submit_order(symbol=ticker, qty=qty, side='buy', type='market',
                                                     time_in_force='day')
                        self.buy_orders[ticker] = datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                    except Exception as e:
                        self.cannot_buy[ticker] = (e, datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
                else:
                    pass

    def alpaca_monitor_positions(self):
        temp_current_position = {}
        all_position_details = self.alpaca_api.list_positions()
        all_order_details = self.alpaca_api.list_orders()
        total_percentage = 0

        for position in all_position_details:
            ticker = f'${position.symbol}'
            temp_dict = dict(current_price=position.current_price, avg_entry_price=position.avg_entry_price,qty=position.qty)
            temp_current_position[ticker] = temp_dict
            percentage = self.percentage_change(float(position.avg_entry_price), float(position.current_price))
            total_percentage = total_percentage + percentage

        self.current_positions = temp_current_position
        self.total_percentage = total_percentage
        self.orders = [f'${order.symbol}' for order in all_order_details]

    def alpaca_sell_ticker(self):
        if self.total_percentage < -10 or self.total_percentage > 10:
            all_position_details = self.alpaca_api.list_positions()
            for position in all_position_details:
                self.alpaca_api.submit_order(symbol=position.symbol, qty=position.qty, side='sell', type='market',
                                             time_in_force='day')
            self.kill_all()


def main():
    twitter_stream_thread = threading.Thread(target=tweet_streamer)
    twitter_stream_thread.start()

    alpaca_api = create_alpaca_api()
    sto = Stock_Trader(alpaca_api)
    #alpaca_api.get_barset('BA', '1Min', limit=10)

    current_moment = datetime.datetime.now()
    start_hour = int(current_moment.strftime('%-H'))
    start_minute = int(current_moment.strftime('%-M'))+1
    start_time = f'{start_hour}:{start_minute}'
    end_time = '12:55'

    console_logger_thread = threading.Thread(target=sto.thread_decorator, args=(sto.console_logger, sto.kill_console_logger, start_time, end_time, 5))
    stock_mentions_thread = threading.Thread(target=sto.thread_decorator, args=(sto.stock_mentions, sto.kill_stock_mentions, start_time, end_time, 5))
    alpca_buy_ticker_thread = threading.Thread(target=sto.thread_decorator, args=(sto.alpca_buy_ticker, sto.kill_alpaca_buy, start_time, end_time, 5))
    alpca_sell_ticker_thread = threading.Thread(target=sto.thread_decorator, args=(sto.alpaca_sell_ticker, sto.kill_alpaca_sell, start_time, end_time, 5))
    alpaca_monitor_positions_thread = threading.Thread(target=sto.thread_decorator, args=(sto.alpaca_monitor_positions, sto.kill_alpaca_monitor, start_time, end_time, 5))


    console_logger_thread.start()
    stock_mentions_thread.start()
    # alpca_buy_ticker_thread.start()
    # alpca_sell_ticker_thread.start()
    # alpaca_monitor_positions_thread.start()

    console_logger_thread.join()
    stock_mentions_thread.join()
    # alpca_buy_ticker_thread.join()
    # alpaca_monitor_positions_thread.join()
    # alpca_sell_ticker_thread.join()


if __name__ == '__main__':
    main()
