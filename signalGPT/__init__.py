import yaml
import openai
from datetime import datetime
import shutil
import os

with open('config.yml','r') as fd:
	config = yaml.load(fd,Loader=yaml.SafeLoader)


openai.api_key = config['apikey']


backupfile = os.path.join("backups",datetime.utcnow().strftime("%Y-%m-%d") + ".sqlite")
shutil.copyfile("database.sqlite",backupfile)
