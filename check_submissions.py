import os
from pathlib import Path
token = Path.home() / '.kaggle' / 'access_token'
os.environ['KAGGLE_API_TOKEN'] = token.read_text().strip()
from kaggle.api.kaggle_api_extended import KaggleApi
api = KaggleApi()
api.authenticate()
subs = api.competition_submissions('kaggriculture')
print('Total submissions:', len(subs))
for s in subs:
    d = s.date.strftime('%m-%d %H:%M') if s.date else 'N/A'
    print('{} | status={} | public={} | private={} | file={}'.format(
        d, s.status, s.public_score, s.private_score, s.file_name))
