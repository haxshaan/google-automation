import os
import logging
import json
from time import sleep
from configparser import ConfigParser
from mysql.connector import connect, Error

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec


base_path = os.getcwd()
driver_path = os.path.join(base_path, 'chromedriver')
user_agent = "Mozilla/5.0 (Windows NT 10.0; ) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36"
login_url = 'https://accounts.google.com/signin'
recovery_check_page_class = "N4lOwd"

logger = logging.getLogger('google_bot')
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


class HaxException(Exception):
    pass


def format_cookies(cookies):
    final: str = ''
    for cookie in cookies:
        final += (cookie['name'] + '=' + cookie['value'] + ';')
    return final


class DriveBot:

    def __init__(self, hostname, db_username, db_password, db_name,
                 table, column, u_name, pass_w, video_info, test_video):
        logger.info("Initializing Hax0 DriveBot, please wait.")
        try:
            logger.info("Creating database connection.")
            self.connection = connect(host=hostname, user=db_username, passwd=db_password, db=db_name)
            # engine = create_engine(f"mysql+mysqlconnector://{user}:{passwd}@{host}:{port}/{database}")
            self.cursor = self.connection.cursor(buffered=True)

        except Error as ex:
            print("Can't connect to database!, error received: ", ex)
            raise SystemExit(0)

        self.url = login_url
        self.video_info_url = video_info
        self.test_video_url = test_video
        self.username = u_name
        self.password = pass_w
        self.table = table
        self.column = column

        options = ChromeOptions()
        options.add_argument(f'user-agent={user_agent}')

        prefs = {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_experimental_option('prefs', prefs)
        options.add_argument('ignore-ssl-errors=yes')
        options.add_argument('ignore-certificate-errors')
        options.add_argument("headless")
        # options.add_argument("remote-debugging-port=9222")
        options.add_argument(f'download.prompt_for_download": True')
        self.driver = webdriver.Chrome(options=options, executable_path=driver_path)
        # self.driver.set_window_size(1120, 550)
        # driver.set_window_position(-10000,0)

    def wait_by_id(self, i, t=5):
        condition = ec.presence_of_element_located((By.ID, i))
        try:
            element = WebDriverWait(self.driver, t).until(condition)
        except Exception as ex:
            self.save_screenshot()
            logger.info(ex)
            element = None
        return element

    def save_screenshot(self, file_name='error_screenshot.png'):
        self.driver.save_screenshot(os.path.join(base_path, file_name))

    def login(self):
        logger.info("Initiating Login flow.")
        try:
            self.driver.get(self.url)

            email_field = self.wait_by_id('identifierId', 10)
            if email_field:
                email_field.clear()
                email_field.send_keys(self.username)
            else:
                raise HaxException("Can't find email field!")

            next_button = self.wait_by_id('identifierNext', 5)
            if next_button:
                self.driver.execute_script("arguments[0].click();", next_button)
            else:
                raise HaxException("Can't find first next button!")

            p_page = self.wait_by_id('password', 10)
            WebDriverWait(self.driver, 5).until(ec.element_to_be_clickable((By.ID, 'password')))

            if p_page:
                p_field = self.driver.find_element_by_css_selector(
                    '#password > div.aCsJod.oJeWuf > div > div.Xb9hP > input'
                )
                p_field.clear()
                p_field.send_keys(self.password)
            else:
                raise HaxException("Can't find password field!")

            final_next_button = self.wait_by_id('passwordNext', 3)
            if final_next_button:
                self.driver.execute_script("arguments[0].click();", final_next_button)
            else:
                raise HaxException("Can't find final next button!")

            WebDriverWait(self.driver, 6).until(ec.presence_of_element_located(
                (By.CLASS_NAME, 'x7WrMb')
            ))

            logger.info("Login successful!")
            return True

        except HaxException as hx:
            logger.info(hx)
            logger.info("Can't log in!")
            self.save_screenshot()
            raise SystemExit(0)

        except Exception as ex:
            logger.info(f"Not logged in!\nException is: {ex}")
            self.save_screenshot()
            raise SystemExit(0)

    def get_session(self):
        sleep(1)
        self.driver.get(self.test_video_url)
        sleep(1)
        self.driver.get(self.video_info_url)
        cookies = self.driver.get_cookies()
        with open(f'cookies.json', 'w+') as f:
            json.dump(cookies, f)
        return cookies

    def save_session_to_file(self):
        cookies = self.get_session()
        session = format_cookies(cookies)
        try:
            with open('cookies.txt', 'w+') as f:
                f.write(session)
        except OSError as ex:
            logger.info(ex)

    def save_to_mysql(self):
        sess = self.get_session()
        cookies = format_cookies(sess)
        print(f"\nSaving into MYSQL DATABASE")
        table_fetch = f"SHOW TABLES FROM {database}"
        self.cursor.execute(table_fetch)
        table_query = [item for item in self.cursor.fetchall()[0]]
        tables = [i.decode() if type(table_query[0]) == bytearray else i for i in table_query]

        if self.table in tables:
            self.cursor.execute(f"SELECT {self.column} FROM {self.table}")
            # current_data = set([i[0] for i in self.cursor.fetchall()])

            try:
                # delete_statement = f"TRUNCATE {self.table};"
                # self.cursor.execute(delete_statement)
                update_statement = f"UPDATE {self.table} SET {self.column} = '{cookies}';"
                self.cursor.execute(update_statement)

            except Error as ex:
                print('Error: ', ex)

            finally:
                logger.info(f"Applying changes to database.")
                self.connection.commit()

            logger.info("\nClosing MySQL connection")
            self.cursor.close()
            self.connection.close()

        else:
            logger.info(f"\nTable named {self.table} does not exist")
            raise SystemExit(0)

    def check_browser(self):
        self.driver.get("https://www.whatismybrowser.com/")
        self.save_screenshot(file_name='user_agent_test_screenshot.png')

    def close_driver(self):
        logger.info(f"Closing driver instance!")
        self.driver.quit()


if __name__ == '__main__':
    parser = ConfigParser()
    parser.read('config.ini')
    try:
        host = parser['MYSQL']['host']
        port = parser['MYSQL']['port']
        db_user = parser['MYSQL']['user']
        db_passwd = parser['MYSQL']['password']
        database = parser['MYSQL']['database']
        table_ = parser['MYSQL']['table']
        column_ = parser['MYSQL']['column']
    except Exception as e:
        logger.info(f"MYSQL config broken!, {e}")
        raise SystemExit(0)

    try:
        username = parser['G_DRIVE']['username']
        password = parser['G_DRIVE']['password']
        video_info_url = parser['G_DRIVE']['video_info_url']
        test_video_url = parser['G_DRIVE']['test_video_url']
    except Exception as e:
        logger.info(f"Google account config broken!, {e}")
        raise SystemExit(0)

    bot = DriveBot(host, db_user, db_passwd, database, table_,
                   column_, username, password, video_info_url, test_video_url)
    try:
        if bot.login():
            bot.save_session_to_file()
            bot.save_to_mysql()
        sleep(5)
    except Exception as e:
        logger.info(e)
    bot.close_driver()
