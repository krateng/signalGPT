import yaml
import openai

with open('config.yml','r') as fd:
	config = yaml.load(fd,Loader=yaml.SafeLoader)
	

openai.api_key = config['apikey']

