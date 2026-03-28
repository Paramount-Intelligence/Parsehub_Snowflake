import requests

resp = requests.get('http://localhost:5000/api/projects')
data = resp.json()

for p in data.get('projects', []):
    title = p.get('title', '')
    if 'chinamachine' in title.lower():
        token = p.get('token')
        proj_id = p.get('id')
        print(f'Found: {title}')
        print(f'Token: {token}')
        print(f'ID: {proj_id}')

        # Check scraped data
        sd_resp = requests.get(f'http://localhost:5000/api/projects/{token}/scraped-data?limit=1000')
        sd_data = sd_resp.json()
        print(f'Scraped Data Count (in this query): {sd_data.get("count", 0)}')
        print(f'Total in Snowflake: {sd_data.get("total", 0)}')

        # Also check scraped_records
        sr_resp = requests.get(f'http://localhost:5000/api/projects/{proj_id}/scraped-records?limit=1000')
        if sr_resp.ok:
            sr_data = sr_resp.json()
            print(f'Scraped Records Count: {sr_data.get("count", 0)}')

        if sd_data.get('data'):
            print(f'Sample record keys: {list(sd_data["data"][0].keys())}')
        else:
            print('No data in scraped_data table')
        print()
