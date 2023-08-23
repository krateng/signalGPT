
function formatTime(timestamp) {
    if (timestamp == null) {
    	return null;
    }
    const date = new Date(timestamp * 1000);
    let hours = date.getHours();
    let minutes = date.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    minutes = minutes < 10 ? '0' + minutes : minutes;
    const timeStr = hours + ':' + minutes + ' ' + ampm;
    return timeStr;
}

function formatDate(timestamp) {
	if (timestamp == null) {
		return null;
	}
	const date = new Date(timestamp * 1000);
	return date.toDateString();
	let year = date.getFullYear();
	let month = date.getMonth() + 1;
	let day = date.getDay() + 1;

	const dateStr = year + '/' + month + '/' + day
	return dateStr;


}

function contextualTimeDescription(timestamp) {
		if (timestamp == null) {
			return null;
		}
		// by chatGPT
    const now = new Date();
    const inputDate = new Date(timestamp*1000);

    const msPerMinute = 60 * 1000;
    const msPerHour = msPerMinute * 60;
    const msPerDay = msPerHour * 24;
    const msPerMonth = msPerDay * 30;  // Average month duration
    const msPerYear = msPerDay * 365;  // Average year duration

    const elapsed = now - inputDate;

    const daysOfWeek = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];


    // If it's today
    if (now.toDateString() == inputDate.toDateString()) {
        return formatTime(timestamp);
    }
    // If it was in the last few days
    else if (elapsed < msPerDay * 5) {
        return daysOfWeek[inputDate.getDay()];
    }
    // If it was at least 5 days ago but less than 8 months
    else if (elapsed < msPerMonth * 8) {
        return inputDate.getDate() + " " + months[inputDate.getMonth()];
    }
    // Older than 8 months
    else {
        return months[inputDate.getMonth()] + " " + inputDate.getFullYear();
    }
		return null;
}



function newDay(timestamp) {
	var today = new Date(timestamp * 1000).toDateString();
	if (this.old_day != today) {
		this.old_day = today;
		return true;
	}
	return false;

}

function getDictValuesByAttribute(dict,attributes,reverse) {
	var sortfunc = function(a,b){
		for (var att of attributes) {
			a = a?.[att] || 0;
			b = b?.[att] || 0;
		}
		return reverse ? (b-a) : (a-b)
	}
	return Object.values(dict).sort(sortfunc)
}

function post(url,data) {
	return fetch(url,{
		method:"POST",
		headers: {
			'Content-Type': 'application/json'
		},
		body:JSON.stringify(data)
	})
}

var converter = new showdown.Converter();

window.appdata = {
	chats:{},
	contacts:{},
	selected_chat:{},
	selectChat(e){
	    for (var element of document.getElementsByClassName("contact")) {
	    	element.classList.remove('selected');
	    }
	    e.currentTarget.classList.add('selected');

	    var uid = e.currentTarget.dataset['chatid'];


	    fetch('/api/chat/' + uid)
	    	.then(response=>response.json())
	    	.then(result=>{
	    		console.log(result);
	    		this.selected_chat = result;
	    		var chatwindow = document.getElementById('chat');

	    		this.manual_update++;
	    		this.$nextTick(()=>{
				chatwindow.scrollTop = chatwindow.scrollHeight;
			});
	    	});
	},
	async getData(){
		await fetch('/api/contacts')
			.then(response=>response.json())
			.then(result=>{
				this.contacts = result;
				this.manual_update++;
			});
		await fetch('/api/conversations')
			.then(response=>response.json())
			.then(result=>{
				this.chats = result;
				this.manual_update++;
			});
		await fetch('/api/userinfo')
			.then(response=>response.json())
			.then(result=>{
				this.userinfo = result;
				this.manual_update++;
			});

	},
	sendMessage(content) {

		var chatwindow = document.getElementById('chat');
		var atEnd = ((chatwindow.scrollTop + 2000) > chatwindow.scrollHeight);

		var timestamp = Math.floor(Date.now() / 1000);
		var msg = {
			own:true,
			content:content,
			timestamp:timestamp
		}



		post("/api/send_message",{
				chat_id: this.selected_chat.uid,
				content: content,
				timestamp: timestamp
			})
				.then(response=>response.json())
				.then(result=>{
					msg.uid = result.uid;
					console.log(msg);
					this.selected_chat.messages.push(msg);
					this.chats[this.selected_chat.uid].latest_message = msg;
					if (atEnd) {
						this.$nextTick(()=>{
							chatwindow.scrollTop = chatwindow.scrollHeight;
						});

					}
				});
	},
	requestResponse() {

		var chatwindow = document.getElementById('chat');
		var atEnd = ((chatwindow.scrollTop + 2000) > chatwindow.scrollHeight);

		fetch("/api/get_message/" + this.selected_chat.uid)
			.then(response=>response.json())
			.then(result=>{
				for (var msg of result.messages) {
					this.selected_chat.messages.push(msg);
					this.chats[this.selected_chat.uid].latest_message = msg;
					if (atEnd) {
						this.$nextTick(()=>{
							chatwindow.scrollTop = chatwindow.scrollHeight;
						});

					}
				}

			});
	},
	findNewContact(searchstr) {
		post("/api/find_contact",{
			'searchstr':searchstr
		})
			.then(response=>response.json())
			.then(result=>{
				var char = result.character;
				var chat = result.chat;
				this.contacts[char.handle] = char;
				this.chats[chat.uid] = chat;
				console.log(result);
			})
	},
	keyboardInput(event) {
		var element = event.target;
		if (element.id == "chat_input_field") {
			if (event.code == "Enter") {
				if (element.value == "") {
					this.requestResponse();
				}
				else {
					this.sendMessage(element.value);
					element.value = "";

				}

			}
			this.updateCurrentInput(element.value);
		}
		else if (element.id == "new_contact_input") {
			if (event.code == "Enter") {
				this.findNewContact(element.value);
				element.value = "";

			}
		}
	},
	updateCurrentInput(content) {
		this.current_input = content;
	},
	completeMention(handle) {
		var inputfield = document.getElementById('chat_input').children[0];
		var content = inputfield.value;
		inputfield.value = content.replace(this.usermatch_regex,'@' + handle + ' ');
		this.updateCurrentInput(inputfield.value);
		inputfield.focus();
	},
	formatMentions(text) {
			for (var user in this.contacts) {
				text = text.replaceAll('@' + user, "<span class='mention'>@" + this.contacts[user].name + "</span>");
			}
			return text;
	},
	editMessage(msg_uid) {
		var element = document.getElementById('message_' + msg_uid);
		var textinput = element.getElementsByClassName('message_text')[0];
		textinput.contentEditable = true;
		textinput.classList.add('editing');
		textinput.focus();
	},
	editMessageSend(msg_uid){
		var element = document.getElementById('message_' + msg_uid);
		var textinput = element.getElementsByClassName('message_text')[0];
		if (textinput.classList.contains('editing')) {
			textinput.classList.remove('editing');
			textinput.contentEditable = false;
			var uid = textinput.dataset.msgid;
			for (var msg of this.selected_chat.messages) {
				if (msg.uid == uid) {
					msg.content = this.html_to_markdown(textinput.innerHTML);
					break;
				}
			}
			this.chats[this.selected_chat.uid].latest_message = this.selected_chat.messages.slice(-1)[0];
			post("/api/edit_message",{
				uid:msg_uid,
				content:this.html_to_markdown(textinput.innerHTML)
			})
		}

	},
	deleteMessage(msg_uid) {
		post("/api/delete_message",{
				uid:msg_uid
		})
			.then(result=>{
				var i = this.selected_chat.messages.length;
				while(i--) {
					if (this.selected_chat.messages[i].uid == msg_uid) {
						this.selected_chat.messages.splice(i,1);
						break;
					}
				}
				this.chats[this.selected_chat.uid].latest_message = this.selected_chat.messages.slice(-1)[0];
			})
	},
	regenerateMessage(msg_uid) {
		post("/api/regenerate_message",{
			uid:msg_uid
		})
			.then(response=>response.json())
			.then(result=>{
				var i = this.selected_chat.messages.length;
				while(i--) {
					if (this.selected_chat.messages[i].uid == msg_uid) {
						this.selected_chat.messages[i].content = result['content'];
						break;
					}
				}
				this.chats[this.selected_chat.uid].latest_message = this.selected_chat.messages.slice(-1)[0];
			})
	},
	addFriend(handle){
		post("/api/add_friend",{
			handle: handle
		})
			.then(result=>{
				this.contacts[handle].friend = true;
			})
	},
	deleteChat(chat_uid) {
		post("/api/delete_chat",{
				uid:chat_uid
		})
			.then(result=>{
				delete this.chats[chat_uid];
				if (this.selected_chat.uid == chat_uid) {
					this.selected_chat = {};
				}
			})
	},
	userinfo:{},
	manual_update:0,
	current_input: "",
	usermatch_regex: /@(\S*$)/g,
	html_to_markdown(html) {
		html = DOMPurify.sanitize(html, {ALLOWED_TAGS:['b','i','strong','li','ol','p','h1','h2','h3','h4']});
		return converter.makeMarkdown(html);
	},
	markdown_to_html(markdown) {
		return converter.makeHtml(markdown);
	}
}


function getAppData() {
	return window.appdata;
}
