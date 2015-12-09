#!/bin/python
import swiftclient
from swiftclient import ClientException
from six.moves import configparser
import os,sys,commands
import datetime
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
import pdb

backup_mysql_name = sys.argv[1]
expire_mysql_name = sys.argv[2]
admin_email = sys.argv[3]
    

logger = None
# Setup global logger
logger_dir=os.getcwd() + "/log/"
if not os.path.exists(logger_dir):
    os.makedirs(logger_dir)

class Config(object):
    def __init__(self, conf_file=None):
        if conf_file:
            self.config_file = conf_file
            self._get_config(specified=True)
        else:
            self._get_config()

    def _get_config(self, specified=False):
        if specified is True:
            config_file = self.config_file
        else:
            config_file = os.environ.get('SWIFTCLIENT_CONFIG_FILE',
                                     './backup.conf')
        config = configparser.SafeConfigParser({'auth_version': '1'})
	config.read(config_file)
        if config.has_section('swiftconf'):
            auth_host = config.get('swiftconf', 'auth_host')
            auth_port = config.getint('swiftconf', 'auth_port')
            auth_ssl = config.getboolean('swiftconf', 'auth_ssl')
            auth_prefix = config.get('swiftconf', 'auth_prefix')
            self.auth_version = config.get('swiftconf', 'auth_version')
            self.account = config.get('swiftconf', 'account')
            self.username = config.get('swiftconf', 'username')
            self.password = config.get('swiftconf', 'password')
            self.container_mysql = config.get('swiftconf', 'container_mysql')
            self.auth_url = ""
            if auth_ssl:
                self.auth_url += "https://"
            else:
                self.auth_url += "http://"
            self.auth_url += "%s:%s%s" % (auth_host, auth_port, auth_prefix)
            if self.auth_version == "1":
                self.auth_url += 'v1.0'
            self.account_username = "%s:%s" % (self.account, self.username)

def create_timed_rotating_log(logfile):
    """"""
    global logger
    logger = logging.getLogger("Rotating Log")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    handler = TimedRotatingFileHandler(logfile,
                                       when="midnight",
                                       interval=1,
                                       backupCount=30)
    handler.setFormatter(fmt)
    if not logger.handlers:
        logger.addHandler(handler)

def remove_expire_object(swiftclient,container_name,object_name):
    logger.info("Starting to remove the expire object : %s" % object_name)
    swiftclient.delete_object(object_name)


def upload_object(swiftclient,container_name,object_name):
    logger.info("Starting to upload the file: %s" % object_name)
    swiftclient.upload(container_name,object_name)
    return True


def send_mail(mail_type):
  #  def _format_addr(s):
  #      name, addr = parseaddr(s)
  #      return formataddr(( \
  #          Header(name, 'utf-8').encode(), \
  #          addr.encode('utf-8') if isinstance(addr, unicode) else addr))
    logger.info("Will send mail to admin!")
    from_addr = "backup_server"
    to_addr = admin_email
    smtp_server = "localhost"
    if mail_type=="successful":
        msg = MIMEText('database %s backup successful!' %,'plain', 'utf-8' )
        msg['Subject'] = Header(u'backup successful!', 'utf-8').encode()

    if mail_type == "error":
        msg = MIMEText('database %s backup failed!' % ,'plain', 'utf-8' )
        msg['Subject'] = Header(u'backup failed!', 'utf-8').encode()


    msg['From'] =  from_addr
    msg['To'] =  to_addr

    server = smtplib.SMTP(smtp_server)
    server.set_debuglevel(1)
    server.sendmail(from_addr, [to_addr], msg.as_string())
    logger.info("send mail finished")
    server.quit()



def main():
	conf = Config()
	logfile= logger_dir + "swiftclient.log"
	print logfile
    	create_timed_rotating_log(logfile)
        conn = swiftclient.Connection(conf.auth_url,
                                      conf.account_username,
                                      conf.password,
                                      auth_version=conf.auth_version)
	logger.info("The swifclient object is %s" % conn)

        # check if container exists, create one if not
        try:
            head_container = conn.head_container(conf.container_mysql)
            logger.info('head container: %s' % json.dumps(head_container,
                sort_keys=True, indent=4))
        except:
            logger.debug('container not exists or swift connection fail...')
            conn.put_container(conf.container_mysql)
            logger.debug('created container...')

    remove_expire_object(conn,container_mysql,expire_mysql_name)

    upload_result = upload_object(conn,container_mysql,backup_mysql_name)
    if upload_result == "True":
        send_mail("successful")
    else:
        send_mail("error")
    
if __name__ == "__main__":
   main()
