import os
import logging
import json
import zipfile
from time import sleep
from configparser import ConfigParser

from mysql.connector import connect, Error
from pyvirtualdisplay import Display

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

debug = False

logger = logging.getLogger('google_bot')
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

base_path = os.getcwd()

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
    table_to_clear = parser['MYSQL']['table_clear']
except Exception as e:
    logger.info(f"MYSQL config broken!, {e}")
    raise SystemExit(0)

try:
    username = parser['G_DRIVE']['username']
    password = parser['G_DRIVE']['password']
    recovery_email = parser['G_DRIVE']['recovery_email']
    video_info_url = parser['G_DRIVE']['video_info_url']
    test_video_url = parser['G_DRIVE']['test_video_url']
except Exception as e:
    logger.info(f"Google account config broken!, {e}")
    raise SystemExit(0)

if parser['PROXY']['use_proxy'].lower() == 'yes':
    use_proxy = True
else:
    use_proxy = False

if use_proxy:
    ip = parser['PROXY']['ip']
    port = parser['PROXY']['port']
    proxy_user = parser['PROXY']['username']
    proxy_pass = parser['PROXY']['password']

    if proxy_user and proxy_pass:
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
        """

        background_js = """
        var config = {
                mode: "fixed_servers",
                rules: {
                  singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                  },
                  bypassList: ["localhost"]
                }
              };
        
        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
        
        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }
        
        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
        );
        """ % (ip, port, proxy_user, proxy_pass)

virtual = True

if virtual:
    display = Display(visible=0, size=(800, 600))
    display.start()

driver_path = os.path.join(base_path, 'chromedriver')

login_url = 'https://accounts.google.com/signin'


class HaxException(Exception):
    pass


def format_cookies(cookies):
    final: str = ''
    for cookie in cookies:
        final += (cookie['name'] + '=' + cookie['value'] + ';')
    return final


class DriveBot:

    def __init__(self, hostname, db_username, db_password, db_name, table, column, u_name,
                 pass_w, video_info, test_video, user_agent=None, headless=False):
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
        self.cookies = None

        options = Options()

        if use_proxy:
            plugin_file = 'proxy_plugin.zip'

            with zipfile.ZipFile(plugin_file, 'w') as zp:
                zp.writestr("manifest.json", manifest_json)
                zp.writestr("background.js", background_js)
            options.add_extension(plugin_file)

        if not user_agent:
            self.user_agent = "Mozilla/5.0 (Windows NT 10.0; ) AppleWebKit/537.36 (KHTML, like Gecko) " \
                                "Chrome/84.0.4147.105 Safari/537.36"
        else:
            self.user_agent = user_agent

        options.add_argument(f'--user-agent={self.user_agent}')

        prefs = {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True
        }
        options.add_experimental_option('prefs', prefs)
        options.add_argument('--ignore-ssl-errors=yes')
        options.add_argument('--ignore-certificate-errors')

        if headless:
            options.add_argument("--headless")

        options.add_argument("window-size=1024,768")
        # options.add_argument("--no-sandbox")
        # options.add_argument("remote-debugging-port=9222")
        options.add_argument('--disable-gpu')
        options.add_argument(f'download.prompt_for_download": True')
        self.driver = webdriver.Chrome(options=options, executable_path=driver_path)
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
        with open('error.html', 'w+') as f:
            f.write(self.driver.page_source)
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

            recovery_page = self.wait_by_id('knowledge-preregistered-email-response', 6)
            if recovery_page:
                WebDriverWait(self.driver, 5).until(ec.element_to_be_clickable(
                    (By.ID, 'knowledge-preregistered-email-response')
                ))
                recovery_field = self.driver.find_element_by_id('knowledge-preregistered-email-response')
                recovery_field.send_keys(recovery_email)

                recovery_button_selector = "#view_container > div > div > div.pwWryf.bxPAYd > div > div.zQJV3 > " \
                                           "div > div.qhFLie > div > div > button"
                WebDriverWait(self.driver, 5).until(ec.element_to_be_clickable(
                    (By.CSS_SELECTOR, recovery_button_selector)
                ))
                recovery_next_button = self.driver.find_element_by_css_selector(recovery_button_selector)
                self.driver.execute_script("arguments[0].click();", recovery_next_button)
            else:
                logger.info("No recovery email confirmation required.")

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
        print(f'Test url is: {self.test_video_url}')
        self.driver.get(self.test_video_url)
        self.save_screenshot('test_video_page.png')
        sleep(1)
        print(f'Info url is: {self.video_info_url}')
        self.driver.get(self.video_info_url)
        self.save_screenshot('video_info.png')

        cookies = self.driver.get_cookies()
        with open(f'cookies.json', 'w+') as f:
            json.dump(cookies, f)
        self.cookies = cookies

    def save_session_to_file(self):
        session = format_cookies(self.cookies)
        try:
            with open('cookies.txt', 'w+') as f:
                f.write(session)
        except OSError as ex:
            logger.info(ex)

    def db_test(self):
        logger.info(f"Running in Debugging mode")
        self.driver.get('https://httpbin.org/ip')

    def save_to_mysql(self):
        cookies = format_cookies(self.cookies)
        print(f"\nSaving into MYSQL DATABASE")
        table_fetch = f"""SHOW TABLES FROM {database};"""
        self.cursor.execute(table_fetch)
        table_query = [item for item in self.cursor.fetchall()]
        tables = [i.decode()[0] if type(table_query[0]) == bytearray else i[0] for i in table_query]

        if self.table in tables:
            column_fetch = f"""SELECT "{self.column}" FROM {self.table};"""
            self.cursor.execute(column_fetch)
            # column_query = [item for item in self.cursor.fetchall()]

            try:
                # delete_statement = f"TRUNCATE {self.table};"
                # self.cursor.execute(delete_statement)
                update_statement = f"""UPDATE {self.table} SET value="{cookies}" WHERE name="{self.column}";"""
                self.cursor.execute(update_statement)

                self.clear_table(table_to_clear)

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

    def clear_table(self, table):
        try:
            clear_query = f"""TRUNCATE TABLE {table};"""
            self.cursor.execute(clear_query)
        except Exception as ex:
            logger.info(f"Can't truncate given table: {ex}")

    def check_ip(self):
        self.driver.get('https://httpbin.org/ip')
        logger.info(f"IP address is: {self.driver.page_source}")

    def check_browser(self):
        self.driver.get("https://www.whatismybrowser.com/")
        self.save_screenshot(file_name='user_agent_test_screenshot.png')

    def close_driver(self):
        logger.info(f"Closing driver instance!")
        self.driver.quit()


if __name__ == '__main__':

    bot = DriveBot(hostname=host, db_username=db_user, db_password=db_passwd,
                   db_name=database, table=table_, column=column_,
                   u_name=username, pass_w=password, video_info=video_info_url,
                   test_video=test_video_url, user_agent=None, headless=False)

    if not debug:
        try:
            # bot.check_ip()
            if bot.login():
                bot.get_session()
                bot.save_session_to_file()
                bot.save_to_mysql()
            bot.close_driver()
        except Exception as e:
            bot.close_driver()
            logger.info(e)
    else:
        bot.db_test()
        bot.close_driver()

    if virtual:
        display.stop()
