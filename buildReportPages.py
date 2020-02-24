"""A simple example of how to access the Google Analytics API."""
import requests
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import jinja2
from datetime import datetime
from collections import defaultdict
import pygal



def jinga2Template(file,args={}):
    templateLoader = jinja2.FileSystemLoader(searchpath="./")
    templateEnv = jinja2.Environment(loader=templateLoader)
    TEMPLATE_FILE = file
    template = templateEnv.get_template(TEMPLATE_FILE)
    outputText = template.render(args)
    return outputText

def get_service(api_name, api_version, scopes, key_file_location):
    """Get a service that communicates to a Google API.

    Args:
        api_name: The name of the api to connect to.
        api_version: The api version to connect to.
        scopes: A list auth scopes to authorize for the application.
        key_file_location: The path to a valid service account JSON key file.

    Returns:
        A service that is connected to the specified API.
    """

    credentials = ServiceAccountCredentials.from_json_keyfile_name(
            key_file_location, scopes=scopes)

    # Build the service object.
    service = build(api_name, api_version, credentials=credentials)

    return service


def get_profile_ids(service):
    # Use the Analytics service object to get the first profile id.

    # Get a list of all Google Analytics accounts for this user
    accounts = service.management().accounts().list().execute()

    if accounts.get('items'):
        # Get the first Google Analytics account.
        for account in  accounts.get('items'):
            prop_name = account.get('name')
            account = account.get('id')

            # Get a list of all the properties for the first account.
            properties = service.management().webproperties().list(
                    accountId=account).execute()
            #print('ervice.management().webproperties()',properties)
            #print()
            properties = properties.get('items')
            if properties:
                # Get the first property id.
                for property in properties:
                    #print('prop',property)
                    #print()
                    property_website = property.get('websiteUrl')
                    ga_code = property.get('id')

                    # Get a list of all views (profiles) for the first property.
                    profiles = service.management().profiles().list(
                            accountId=account,
                            webPropertyId=ga_code).execute()
                    #print('service.management().profiles().list',profiles)
                    #print()
                    profiles= profiles.get('items')
                    if profiles:
                        # return the first view (profile) id.
                        for pro in profiles:
                            yield (prop_name,ga_code.strip(),property_website,pro.get('id'))

    return None


def get_results(service, profile_id,start_date, end_date, metrics, dimensions):
    # Use the Analytics Service Object to query the Core Reporting API
    # for the number of sessions within the past seven days.
    return service.data().ga().get(
            ids='ga:' + profile_id,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            dimensions=dimensions
    ).execute()

class TableBuilder():
    rows=[]
    row = []
    def __init__(self,class_name=''):
        self.reset()
        self.class_name=class_name
    def reset(self):
        self.row = ['<tr>']
        self.rows=[]
    def newRow(self):
        self.row.append('</tr>')
        self.rows.append('\n'.join(self.row))
        self.row = ['<tr>']
    def append(self,data):
        self.row.append('<td>{}</td>'.format(data))
    def __str__(self):
        return "<table class='{}'>\n".format(self.class_name) + '\n'.join(self.rows) + "\n</table>"

        
def print_page_view_results(results):
    t= TableBuilder('minimalistBlack')
    t.append('&nbsp;')
    t.append('Url')
    t.append('Title')
    t.append('Page Views')
    t.append('Percent Of Total')
    t.newRow()
    tot=0
    # Print data nicely for the user.
    if results:
        sessions = "None"
        pages_views = results.get('rows')
        if pages_views is not None:
            pages_views = sorted(pages_views, key=lambda k: int(k[2]), reverse=True) 
            
            for row in pages_views:
                tot += int(row[2])
            for index,row in enumerate(pages_views):
                t.append('{}'.format(index))
                t.append('{}'.format(row[1]))
                t.append('{}'.format(row[0]))
                t.append('{}'.format(row[2]))
                t.append('{}'.format(round((int(row[2])/tot)*100, 2)))
                t.newRow()
    else:
        t.append('\tNo results found')
    return tot,str(t)

import re
re_find_ga = re.compile('\'(UA-[A-Z0-9\-]*)\'')
def getGa(url):
    txt = requests.get(url).text
    a = re_find_ga.search(txt)
    if a:
        return a[1].strip()
    else:
        return 'NONE FOUND'
    

def LineGraph(title,data):
    chart = pygal.Line(x_label_rotation=45,height=200,show_legend = False)
    mark_list = list(data.values())
    chart.add(title,mark_list)
    chart.x_labels = list(data.keys())
    return chart.render().decode('utf-8-sig').replace("<title>Pygal</title>","<title>{}</title>".format(title))



def getGraph(results):
    data = defaultdict(int)
    # Print data nicely for the user.
    if results:
        sessions = "None"
        pages_views = results.get('rows')
        if pages_views is not None:
            for index,row in enumerate(pages_views):
                date = row[0]
                date = datetime.strptime(date, '%Y%m%d').strftime('%m-%d-%Y')
                
                data[date] += int(row[1])
        
    return dict(data)

def main():
    start_date = '30daysAgo'
    end_date = 'today'
    key_file_location = './service_account_config.json'
    # Define the auth scopes to request.
    scope = 'https://www.googleapis.com/auth/analytics.readonly'

    # Authenticate and construct service.
    service = get_service(
            api_name='analytics',
            api_version='v3',
            scopes=[scope],
            key_file_location=key_file_location)

    for name, ga_code, property_website, profile_id in get_profile_ids(service):
        print(name,' - ',profile_id , ' - ' , ga_code)
        
        
        total_page_views, page_view_results = print_page_view_results(
            get_results(
                service,
                profile_id,
                start_date,
                end_date,
                'ga:hits',
                'ga:pagePath,ga:pageTitle'
            )
        )
        if page_view_results.strip() == '':
            page_view_results ="No Page Views this month."
            
        graph_data = getGraph(
            get_results(
                service,
                profile_id,
                start_date,
                end_date,
                'ga:hits',
                'ga:date'
            )
        )
        graph = LineGraph('Page Views',graph_data)
        date = str(datetime.now().date())
        site_ga_code = getGa(property_website)
        status =  "red"
        if site_ga_code ==ga_code:
            status ='green'
        my_end_date = end_date
        if end_date == 'today':
            my_end_date = datetime.now().strftime('%m-%d-%Y')
        html = jinga2Template('templates/report.template.html',{
            'error':'',
            'graph_svg':graph,
            'total_page_views':total_page_views,
            'page_view_results':page_view_results,
            'name':name,
            'ga_code':ga_code,
            'site_ga_code':site_ga_code,
            'property_website':property_website,
            'check_color':status,
            'status': str(status == 'green'),
            'start_date':start_date,
            'end_date':my_end_date,
            'date':date
        })
        if total_page_views>0:
            with open('./GA_{} {}.html'.format(name, date),'w') as f:
                f.write(html)
        print()  


if __name__ == '__main__':
    main()