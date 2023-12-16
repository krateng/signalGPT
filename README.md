## SignalGPT

This started off as a frontend for the OpenAI API in order to have different personas for the AI that specialize in different topics and have their own characters.
Now it can pretty much be used as a sort of AI companion - the AI can send memes, selfies, introduce you to their friends, rename the group chat for comedic effect etc. :D

It is highly recommended to use GPT-4 for chats, and almost obligatory for meta-prompts - but this can get very expensive. Check your usage statistics regularly!

### Work in Progress

Right now there is very little web interface feedback. Keep your terminal open to see when requests haven't succeeded.

### Deployment

* Bare metal: Install with `pip install .` Run with `python3 -m signalGPT.web` in an empty folder.
* Container: Mount your data directory to `/data` inside the container. Map your desired port to `9090`.

Make sure to add your OpenAI API key to the config file.
You should also add a getimg.ai key for image generation.
Authentication is very basic. It is not recommended to expose this service to the web.
