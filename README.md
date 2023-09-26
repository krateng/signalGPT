## SignalGPT

This started off as a frontend for the OpenAI API in order to have different personas for the AI that specialize in different topics and have their own characters.
Now it can pretty much be used as a sort of AI companion - the AI can send memes, selfies, introduce you to their friends, rename the group chat for comedic effect etc. :D

It is highly recommended to use GPT-4 for longer chats, and almost obligatory for meta-prompts - but this can get very expensive. Check your usage statistics regularly!

### Work in Progress

Right now the application takes your authentication for Anydream (Image generation) directly from the browser, so it won't work on a server / containerized.
There is very little web interface feedback. Keep your terminal open to see when requests haven't succeeded.

### Deployment

* Bare metal: Install with `pip install .` Run with `python3 -m signalGPT.web` in an empty folder.
* Container: Mount your data directory to `/data` inside the container. Map your desired port to '8080'.

Make sure to add your OpenAI API key to the config file.
Careful, there is zero authentication! Don't expose to the web.
