import enum

from .. import config


Capability = enum.Enum('Capability',[
	'ImageGeneration'
])

def singleton(cls):
	return cls()

class AIProvider:
	options = {
		cap: []
		for name,cap in Capability._member_map_.items()
	}


	def __init_subclass__(cls,**kwargs):
		pass


	def __init__(self):
		self.auth = config.get('auth',{}).get(self.identifier,{})
		basecls = self.__class__.__base__
		for cap in self.capabilities:
			basecls.options[cap].append(self)
			#basecls.options.setdefault(cap,{})[self.identifier] = self



	@classmethod
	def __getitem__(cls,attr):
		return cls.options[attr]

from . import anydream, openai

AI = {
	name: [provider for provider in AIProvider.options[cap] if provider.identifier == config['use_service'][name]][0]
	for name,cap in Capability._member_map_.items()
}
