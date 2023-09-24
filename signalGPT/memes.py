from pprint import pprint

templates = {
	'distracted_boyfriend':{
		"captions":[
			"walking_girl","boyfriend","girlfriend"
		],
		"id":"db",
		"name": "Distracted Boyfriend"
	},
	'drake':{
		"captions":[
			"drake_decline","drake_approve"
		],
		"id":"drake",
		"name": "Drake"
	},
	'captain_america':{
		"captions":[
			"captain_hook","sitwell_response","captain_punchline"
		],
		"id":"captain-america",
		"name": "Captain America Elevator Fight"
	},
	'buyaboat':{
		"captions":[
			None,
			"cat"
		],
		"id":"boat",
		"name": "I should buy a boat cat"
	},
	'alwayshasbeen':{
		"captions":[
			"surprised_astronaut_speech",
			"traitor_astronaut_speech",
			"surprised_astronaut_name",
			"traitor_astronaut_name"
		],
		"id":"astronaut",
		"name": "Always has been astronaut"
	},
	'expandingbrain':{
		"captions":[
			"small_brain","medium_brain","big_brain","galaxy_brain"
		],
		"id":"gb",
		"name":"Expanding Brain"
	}
}


escape = {
	"?":"~q",
	"&":"~a",
	"/":"~s"
}
def escape_captions(captions):
	for i,j in escape.items():
		captions = [
			c.replace(i,j)
			for c in captions
		]

	return captions

def create_memecreation_func(templatename):
	templateinfo = templates[templatename]
	def create_meme(templateinfo=templateinfo,**captions):
		captionfields = templateinfo['captions']
		captionvalues = [(captions[f"caption_{c}"] if c else "_") for c in captionfields]
		return {
			'image':f"https://api.memegen.link/images/{templateinfo['id']}/{'/'.join(escape_captions(captionvalues))}.png",
			'desc': f"A {templateinfo['name']} meme with the caption: " + " / ".join(captionvalues)
		}
	return create_meme

def get_functions():

	return {
		f"send_meme_{templatename}": {
			'schema':{
				'name': f"send_meme_{templatename}",
				'description': f"Send a {template['name']} meme",
				'parameters':{
					'type':'object',
					'required': [f"caption_{name}" for name in template['captions']],
					'properties':{
						f"caption_{name}": {'type':"string"}
						for name in template['captions']
					}
				}
			},
			'func': create_memecreation_func(templatename)
		}

		for templatename,template in templates.items()
	}
