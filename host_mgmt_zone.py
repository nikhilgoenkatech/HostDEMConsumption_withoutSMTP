import os
import io
import sys  
import json
import requests 
import logging
import traceback
import xlsxwriter
from constant_host_unit import *
sys.path.append("")

hostList = [] 

class app:
  def __init__(self):
   self.name = ""
   self.type = ""
   self.entityId = ""
   self.consumption = 0
   self.dem = 0


class tenantInfo:
   def __init__(self):
     self.tenant_url = ""
     self.tenant_token = ""
     self.name = ""

#------------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to make API call using the token defined in constant.py
# Returns the json object returned using the API call 
#------------------------------------------------------------------------------
def dtApiQuery(logger, endpoint, tenant_info, URL=""):
  try: 
    logger.info("In dtApiQuery")

    if URL == "":
      URL = tenant_info.tenant_url

    query = str(URL) + str(endpoint)
    get_param = {'Accept':'application/json', 'Authorization':'Api-Token {}'.format(tenant_info.tenant_token)}
    populate_data = requests.get(query, headers = get_param)
    data = populate_data.json()
    logger.info("Execution sucessfull: dtApiQuery")

  except Exception as e:
    logger.error("Received exception while running dtApiQuery", exc_info = e) 

  finally:
    return data
#---------------------------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to print the entire structure of app_mgmt_zone (will be used for debugging) 
#---------------------------------------------------------------------------------------------
def pretty_print(logger, app_mgmt_zone):
  try:
    logger.info("In pretty_print")
    for mgmt_zone_name in app_mgmt_zone.keys():
        for i in range(len(app_mgmt_zone[mgmt_zone_name])):
          print (mgmt_zone_name + " " + str(len(app_mgmt_zone[mgmt_zone_name])) + "." + app_mgmt_zone[mgmt_zone_name][i].name + "\t" + str(app_mgmt_zone[mgmt_zone_name][i].consumption) + "\t" + str(app_mgmt_zone[mgmt_zone_name][i].dem) + "\n")
  except Exception as e:
    logger.fatal("Received exception while running pretty_print", str(e), exc_info=True)


def write_data(logger, worksheet, tenant_info, mgmt_zone, app_mgmt_zone):
    try:
      logger.info("In write_data: ")
      j = 0 
      for key in mgmt_zone.keys():
        try:
          total_consumption = 0
          for i in range(len(app_mgmt_zone[key])):
            total_consumption = total_consumption + app_mgmt_zone[key][i].dem
        except KeyError:
          total_consumption = 0.0
        finally:
          j = j + 1
          worksheet.write(j,0,str(key))
          worksheet.write(j,1,float(mgmt_zone[key]))
          worksheet.write(j,2,float(total_consumption))
 
      for key in app_mgmt_zone.keys():
        total_consumption = 0
        for i in range(len(app_mgmt_zone[key])):
          total_consumption = float(total_consumption) + app_mgmt_zone[key][i].dem

        try:
          host_units = mgmt_zone[key]
        except KeyError:
          host_units = "0.0"
        finally:
          j = j + 1
          worksheet.write(j,0,str(key))
          worksheet.write(j,1,float(host_units))
          worksheet.write(j,2,float(total_consumption))
 
    except Exception:
      logger.error ("Received error while executing write_data ", exc_info=e)
     
    finally:
      return worksheet

#------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to call API and populate the excel file
#------------------------------------------------------------------------
def func(logger, totalHostUnits, tenant_info, workbook, mgmt_zone, app_mgmt_zone):
  try:
    logger.info("In func")
    logger.debug("func: totalHostUnits = %s", totalHostUnits)  

    hosts = dtApiQuery(logger, INFRA_API, tenant_info)

    for host in hosts:
      key = ""
      #Management Zone
      try:
        zones = host['managementZones']
        for zone in zones:
          key = key + zone['name'] + ","
        key = key[:-1]
      except KeyError:
        key = "No assigned management zone"

      try:
        mgmt_zone[key] = mgmt_zone[key] + float(host['consumedHostUnits'])
      except KeyError:
        mgmt_zone[key] = float(host['consumedHostUnits']) 
    
      #print "Host -> ", host['displayName'] +  " -> " + str(key) + " -> " + str(mgmt_zone[key])

    #First fetch all the applications
    app_mgmt_zone = fetch_application(logger, app_mgmt_zone, tenant_info, FETCH_APPLICATIONS)

    #Now fetch all the synthetic applications 
    app_mgmt_zone = fetch_syn_application(logger, app_mgmt_zone, tenant_info, FETCH_SYN_APPLICATIONS)

    app_mgmt_zone = populate_consumption(logger, app_mgmt_zone, tenant_info, APP_BILLING_API)
    app_mgmt_zone = populate_consumption(logger, app_mgmt_zone, tenant_info, SYN_BILLING_API, 1)
    app_mgmt_zone = populate_consumption(logger, app_mgmt_zone, tenant_info, HTTP_BILLING_API, 2)
   
    worksheet = workbook.add_worksheet(tenant_info.name) 
    #pretty_print(logger, app_mgmt_zone)        
    worksheet.write(0,0,"Management Zone")
    worksheet.write(0,1,"Host Units Consumption")
    worksheet.write(0,2,"DEM Units Consumption")
    worksheet = write_data(logger, worksheet, tenant_info, mgmt_zone, app_mgmt_zone)
    logger.info("Successful execution: func")
    
  except Exception as e:
    logger.fatal("Received exception while running func", str(e), exc_info = True)

  finally:
    return workbook

#------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to fetch all the synthetic browsers and append it to the directory "app_mgmt_zone" 
#------------------------------------------------------------------------
def populate_consumption(logger, app_mgmt_zone, tenant_info, query, syn = 0):
  consumption_details = {}
  try:
    logger.info("In populate_consumption")
    logger.debug("populate_consumption = %s", query)
   
    url = (tenant_info.tenant_url).replace("v1","v2")
    applications = dtApiQuery(logger, query, tenant_info, url)

    if syn == 0:
      apps = applications['result'][0]['data']
    elif syn == 1:
      apps = applications['result'][0]['data']
    elif syn == 2:
      apps = applications['result'][0]['data']

    for billing in apps:
      dimensions = billing['dimensions']
      if syn == 0:
        if dimensions[1] == "Billed":
          consumption_details[dimensions[0]] = billing['values'][0]
      elif syn >= 0:
          consumption_details[dimensions[0]] = billing['values'][0]
    logger.info("Successful execution: populate_consumption")
    
    for key in consumption_details.keys():
      for mgmt_zone_name in app_mgmt_zone.keys():
        for i in range(len(app_mgmt_zone[mgmt_zone_name])):
          if key == app_mgmt_zone[mgmt_zone_name][i].entityId:
            app_mgmt_zone[mgmt_zone_name][i].consumption = app_mgmt_zone[mgmt_zone_name][i].consumption + consumption_details[key]

            if app_mgmt_zone[mgmt_zone_name][i].type == "Synthetic":
              app_mgmt_zone[mgmt_zone_name][i].dem = float(app_mgmt_zone[mgmt_zone_name][i].consumption * 1.0)

            elif app_mgmt_zone[mgmt_zone_name][i].type == "HTTP":
              app_mgmt_zone[mgmt_zone_name][i].dem = float(app_mgmt_zone[mgmt_zone_name][i].consumption * 0.1)

            else: 
              app_mgmt_zone[mgmt_zone_name][i].dem = float(app_mgmt_zone[mgmt_zone_name][i].consumption * 0.25)

  except Exception as e:
    logger.fatal("Received exception while running populate_consumption", exc_info=e)
    
  finally:
    return app_mgmt_zone

#------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to fetch all the synthetic browsers and append it to the directory "app_mgmt_zone" 
#------------------------------------------------------------------------
def fetch_syn_application(logger, app_mgmt_zone, tenant_info, query):
  try:
    logger.info("In fetch_syn_application")
    logger.debug("fetch_syn_application = %s", query)
   
    #print query
    applications = dtApiQuery(logger, query, tenant_info)
   
    application = applications['monitors']

    for i in range(len(application)):
      appInfo = app()
      appInfo.name = application[i]['name']

      #For custom-type application, applicationType is not populated, hence the check
      try:
        if application[i]['type'] is not "HTTP":
          appInfo.type = "Synthetic"
        else:
          appInfo.type = "HTTP"
      except KeyError:
        appInfo.type = "Synthetic"
          
      appInfo.entityId = application[i]['entityId']
 
      #Management Zone
      key = ""
      try:
        zones = application[i]['managementZones']
        for zone in zones:
          key = key + zone['name'] + ","
        key = key[:-1]
      except KeyError:
        key = "No management zone"

      if key in app_mgmt_zone.keys():
        app_mgmt_zone[key].append(appInfo)
      else:
        app_mgmt_zone[key] = [appInfo]
 
    logger.info("Successful execution: fetch_sync_application")
    
  except Exception as e:
    logger.fatal("Received exception while running fetch_syn_application ", str(e), exc_info=True)

  finally:
    return app_mgmt_zone

#------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to call API and populate the excel file
#------------------------------------------------------------------------

def fetch_application(logger, app_mgmt_zone, tenant_info, query):
  try:
    logger.info("In fetch_application")
    logger.debug("fetch_application = %s", query)
   
    #print query
    applications = dtApiQuery(logger, query, tenant_info)

    for application in applications:
      appInfo = app()
      appInfo.name = application['displayName']

      #For custom-type application, applicationType is not populated, hence the check
      try:
        appInfo.type = application['applicationType']
      except KeyError:
        appInfo.type = "Not available"

      appInfo.entityId = application['entityId']
 
      key = ""
      #Management Zone
      try:
        zones = application['managementZones']
        for zone in zones:
          key = key + zone['name'] + ","
        key = key[:-1]
      except KeyError:
        key = "No management zone"

      if key in app_mgmt_zone.keys():
        app_mgmt_zone[key].append(appInfo)
      else:
        app_mgmt_zone[key] = [appInfo]
   
    logger.info("Successful execution: fetch_application")
    
  except Exception as e:
    logger.fatal("Received exception while running fetch_application ", exc_info=e)

  finally:
    return app_mgmt_zone
#------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to call API and populate the excel file
#------------------------------------------------------------------------
def parse_config(filename):
  try:
    stream = open(filename)
    data = json.load(stream)
  except Exception:
    logger.error("Exception encountered in parse_config function : %s ", exc_info=e)
  finally:
    return data


#------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to call API and populate the excel file
#------------------------------------------------------------------------
def populate_tenant_details(logger, tenant, tenant_info):
  try:
    logger.info("In populate_tenant_details")
    logger.info("In populate_tenant_details %s ", tenant)

    tenant_info.tenant_url = tenant['tenant-URL'] 
    tenant_info.tenant_token = tenant['API-token']
    tenant_info.name = tenant['tenant-name']
  except Exception as e:
    logger.error("Exception encountered while executing populate_tenant_details %s ", str(e))
  finally:
    return tenant_info 
  
#------------------------------------------------------------------------
# Author: Nikhil Goenka
# Function to call API and populate the excel file
#------------------------------------------------------------------------

if __name__ == "__main__":
  try:
    totalHostUnits = 0
    filename = "config.json"
    data = parse_config(filename)


    logging.basicConfig(filename=data['log_file'],
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)
    logger = logging.getLogger()
    tenants = data['tenant-details']

    workbook = xlsxwriter.Workbook("Consumption_details.xlsx") 
    for tenant in tenants:
      mgmt_zone = {}
      app_mgmt_zone = {} 

      tenant_info = tenantInfo()
      tenant_info = populate_tenant_details(logger, tenant, tenant_info)
      workbook = func(logger, totalHostUnits, tenant_info, workbook, mgmt_zone, app_mgmt_zone)
   
  except Exception as e:
    logger.error("Received exception while running main", exc_info=e)
  
  finally:
    logger.info("Succesfull completion of running the program")
    workbook.close()
