#!/bin/env python

import sys
import requests
from requests.auth import HTTPBasicAuth
import json
import pprint
import argparse
import os
import datetime





class AbbAccess():
    def __init__(self,username, password):
        self._username = username
        self._password = password

        self._session = None
        return


    def _get_session(self):
        #check if one already exists
        loginorigin = "https://www.auroravision.net/ums/v1/loginPage"
        loginurl = "https://www.auroravision.net/ums/v1/login?setCookie=true"

        if not self._session:
            reqsession = requests.Session()

            req = reqsession.get(loginorigin)
            req = reqsession.get(loginurl, auth=HTTPBasicAuth(self._username, self._password))
            self._session = reqsession

        return self._session


    def get_report(self,startdate,enddate):
        #get the daily report for a date range
        reporturl = "https://easyview.auroravision.net/easyview/services/gmi/summary/GenerationEnergy.json?type=GenerationEnergy&eids=14349631&tz=US%2FPacific&start={}&end={}&range=7D&hasUsage=false&label=7D&dataProperty=chartData&binSize=Hour&bins=true&plantPowerNow=false&v=2.1.51"
        reqsession = self._get_session()
        req = reqsession.get(reporturl.format(startdate,enddate))
        #pprint.pprint(req.text)
        return req.json()

    def get_usage_date(self,usagedate):
        datestring = usagedate.strftime("%Y%m%d")
        startdate = (usagedate - datetime.timedelta(days=6)).strftime("%Y%m%d")
        enddate = (usagedate + datetime.timedelta(days=1)).strftime("%Y%m%d")
        result = self.get_report(startdate,enddate)


        #pprint.pprint(result)

        for field in result['fields']:
            if field['type'] == "bins":
                for value in field['values']:
                    if value['startLabel'].startswith(usagedate.strftime("%Y%m%d")):
                        usage = float(value['value'])
        return usage



if __name__ == '__main__':
    username = None
    password = None

    parser = argparse.ArgumentParser(description='pull report from generation')
    parser.add_argument("-u", "--username", dest="username", help="Username")
    parser.add_argument("-p", "--password", dest="password", help="Password")
    parser.add_argument("-y", "--yesterday",
                        action="store_true",
                        dest="yesterday",
                        default=False,
                        help="output yesterday's generation")

    args = parser.parse_args()
    
    if args.username:
        username = args.username
    else:
        username = input("Utente:\n")
    if args.password:
        password = args.password
    else:
        password = input("Password:\n")

    access = AbbAccess(username, password)

    if args.yesterday:
        yesterday_date = datetime.date.today() - datetime.timedelta(days=1)
        result = access.get_usage_date(yesterday_date)
        pprint.pprint(result)
    else:
        startdate = "20250101"
        enddate = "20250101"

        result = access.get_report(startdate,enddate)
        pprint.pprint(result)
