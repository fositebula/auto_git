# coding=utf-8
import time
from requests import ConnectionError

import git
import requests
import json
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from requests import ConnectionError
from smtpd import COMMASPACE
import smtplib

import logging
import logging.handlers

logger = logging.getLogger(__name__)

#for gerrit
USER = 'dongpl'
PASSWD = 'dongpl123'

#for mail
TO_SOMEONE = ["dongpl@spreadst.com"]
MAIL_ACCOUNT = "pl.dong@spreadtrum.com"
PASSWD = "123@afAF"
MAIL_FROM = "Auto Git <pl.dong@unisoc.com>"
SMPT_HOST = "smtp.unisoc.com"
SMPT_PORT = 587
DOCMD = "ehlo"

#for logger
LOG_FILE = "./autogit.log"
LOG_LEVEL = logging.INFO

#return code
FAIL = 'Fail'
SUCCESS = 'Success'
NO_CHANGE = 'No Change'

#git repository path
GIT_REPOSITORY_path = 'autogit'

def logger_init():
    logger.setLevel(level = LOG_LEVEL)
    handler = logging.FileHandler(LOG_FILE)
    handler.setLevel(LOG_LEVEL)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def send_mail(sub, content, send_mail_list):
    try:
        mail_obj = smtplib.SMTP(SMPT_HOST, SMPT_PORT)
        mail_obj.docmd(DOCMD, MAIL_ACCOUNT)
        mail_obj.starttls()
        mail_obj.login(MAIL_ACCOUNT, PASSWD)
        msg = MIMEMultipart()
        msg['From'] = MAIL_FROM
        msg['To'] = COMMASPACE.join(send_mail_list)
        msg['Subject'] = sub
        con = MIMEText(content, 'html', 'utf-8')
        msg.attach(con)
        mail_obj.sendmail(MAIL_ACCOUNT, send_mail_list, msg.as_string())
        mail_obj.quit()
    except:
        traceback.print_exc()
        logger.error(traceback.format_exc())

def main(message):
    repo = git.Repo(GIT_REPOSITORY_path)
    if not repo.is_dirty():
        print NO_CHANGE
        return
    commit_id = repo.heads[0].commit.hexsha
    git = repo.git
    try:
        git.add(['compile.json'])
        git.commit(['-m', message])
        ret = git.push(['ssh://dongpl@review.source.spreadtrum.com:29418/lava_apr/lava_submit_server', 'HEAD:refs/for/master'])
    except git.GitCommandError:
        send_mail('Auto Git Main GitCommandError', traceback.format_exc(), TO_SOMEONE)
        print FAIL
        return
    ret = gerrit_verify_review_submit(commit_id)
    print ret

def gerrit_verify_review_submit(commitid):
    def _get_gerrit_id(s, commitid):
        qurl = 'http://review.source.spreadtrum.com/gerrit/changes/?q={}&n=25&O=81'.format(commitid)
        response_data = s.get(qurl)
        j_str =  response_data.content[4:]
        j_data = json.loads(j_str)
        gerrit_id = j_data[0]['_number']
        return gerrit_id
    try:
        s = requests.Session()
        res = s.get("http://review.source.spreadtrum.com/gerrit/login/", auth=(USER, PASSWD))
        #获取gerritid
        gerritid = _get_gerrit_id(s, commitid)
        print 'Gerrit ID :', gerritid
        #获取X-Gerrit-Auth
        res = s.get("http://review.source.spreadtrum.com/gerrit/changes/?q=change:{}+has:draft&O=0".format(gerritid))
        headers = res.request.headers
        X_Gerrit_Auth = headers['Cookie'].split('=')[-1]
        headers['X-Gerrit-Auth'] = X_Gerrit_Auth

        #执行打分并合入
        verify_review_url = 'http://review.source.spreadtrum.com/gerrit/changes/{}/revisions/{}/review'.format(gerritid, commitid)
        submit_url = 'http://review.source.spreadtrum.com/gerrit/changes/{}/revisions/{}/submit'.format(gerritid, commitid)
        post_data = {"labels":{"Code-Review":2,"Verified":1},"strict_labels":True,"drafts":"PUBLISH_ALL_REVISIONS"}
        res = s.post(verify_review_url, headers=headers, json=post_data)
        print res.status_code
        res = s.post(submit_url, headers=headers, json=post_data)
        print res.status_code
        if res.status_code == 200:
            return SUCCESS
    except ConnectionError:
        send_mail('Auto Git ConnectionError', "ConnectionError", TO_SOMEONE)
        time.sleep(18)
        gerrit_verify_review_submit(commitid)
    except:
        send_mail('Auto Git exception', traceback.format_exc(), TO_SOMEONE)
        return FAIL


if __name__ == '__main__':
    main()