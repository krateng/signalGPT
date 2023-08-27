
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


function sameDay(a,b) {
	if ((a == undefined) || (b == undefined)) {
		return false;
	}
	var a_str = new Date(a * 1000).toDateString();
	var b_str = new Date(b * 1000).toDateString();
	return (a_str == b_str);
}

function arrayValueAndPrev(element,index,array) {
	return [array[index-1],element]
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

function patch(url,data) {
	return fetch(url,{
		method:"PATCH",
		headers: {
			'Content-Type': 'application/json'
		},
		body:JSON.stringify(data)
	})
}

function del(url,data) {
	return fetch(url,{
		method:"DELETE",
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
	selectChat(uid){
	    for (var element of document.getElementsByClassName("contact")) {
	    	element.classList.remove('selected');
	    }
			document.getElementById("chat_" + uid).classList.add('selected');

			if (this.chats[uid].full_loaded) {
				this.selected_chat = this.chats[uid];
				var chatwindow = document.getElementById('chat');

				this.$nextTick(()=>{
					chatwindow.scrollTop = chatwindow.scrollHeight;
				});
			}
			else {
				fetch('/api/chat/' + uid)
		    	.then(response=>response.json())
		    	.then(result=>{
		    		console.log(result);
						this.chats[uid] = result;
						this.chats[uid].full_loaded = true;
		    		this.selectChat(uid);
		    	});
			}

	},
	async getData(){
		await fetch('/api/contacts')
			.then(response=>response.json())
			.then(result=>{
				this.contacts = result;
			});
		await fetch('/api/conversations')
			.then(response=>response.json())
			.then(result=>{
				this.chats = result;
			});
		await fetch('/api/userinfo')
			.then(response=>response.json())
			.then(result=>{
				this.userinfo = result;
			});

	},
	sendMessage(content,media) {

		var chatwindow = document.getElementById('chat');
		var atEnd = ((chatwindow.scrollTop + 2000) > chatwindow.scrollHeight);

		var timestamp = Math.floor(Date.now() / 1000);

		post("/api/send_message",{
				chat_id: this.selected_chat.uid,
				content: content,
				media: media,
				timestamp: timestamp
			})
				.then(response=>response.json())
				.then(result=>{
					console.log(result);
					this.selected_chat.messages.push(result);
					this.chats[this.selected_chat.uid].latest_message = this.selected_chat.messages.slice(-1)[0];
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
		post("/api/contact",{
			desc:searchstr
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
			if (event.code == "Enter" && !event.shiftKey) {
				if (element.value == "") {
					this.requestResponse();
				}
				else {
					this.sendMessage(element.value,null);
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
		var inputfield = document.getElementById('chat_input_field');
		var content = inputfield.value;
		inputfield.value = content.replace(this.usermatch_regex,'@' + handle + ' ');
		this.updateCurrentInput(inputfield.value);
		inputfield.cursorposition = inputfield.value.length;
		inputfield.focus();
	},
	formatMentions(text) {
			for (var user in this.contacts) {
				text = text.replaceAll('@' + user, "<span class='mention'>@" + this.contacts[user].name + "</span>");
			}
			return text;
	},


	/// CHATS
	postGroup() {
		post("/api/groupchat",{})
			.then(response=>response.json())
			.then(result=>{
				this.chats[result.uid] = result;
				this.selected_chat = result;
			})
	},
	patchChat(data) {
		patch("/api/chat",data)
			.then(response=>response.json())
			.then(result=>{
				this.chats[result.uid] = result;
				this.selected_chat = result;
			})
	},
	changeChatPicture(event) {
		event.preventDefault();
		var chatinfowindow = document.getElementById('chat_info');
		chatinfowindow.style.backgroundColor='';

		var uid = this.selected_chat.uid;

		const file = event.dataTransfer.files[0];
		if (file) {
			const formData = new FormData();
			formData.append('file', file);
			fetch('/api/upload_media', {
		      method: 'POST',
		      body: formData,
		    })
		    .then((response) => response.json())
		    .then((result) => {
					if (this.chats[uid].groupchat) {
						this.patchChat({uid:uid,image:result.path})
					}
					else {
						this.patchContact({handle:this.chats[uid].partner,image:result.path})
						// locally adjust chat to have same img
						this.chats[uid].image = result.path;
					}

		    })
		}

	},
	editChatName() {
		var textinput = document.getElementById('chat_name');
		textinput.contentEditable = true;
		textinput.classList.add('editing');
		textinput.focus();
	},
	editChatNameSend() {
		var textinput = document.getElementById('chat_name');
		if (textinput.classList.contains('editing')) {
			textinput.classList.remove('editing');
			textinput.contentEditable = false;
			textinput.innerHTML = textinput.textContent;
			if (this.selected_chat.groupchat) {
				this.patchChat({uid:this.selected_chat.uid,name:textinput.textContent});
			}
			else {
				this.patchContact({handle:this.selected_chat.partner,name:textinput.textContent});
			}

		}
	},
	// these are technically both contact edits, but... eh, you understand
	editChatDesc() {
		var textinput = document.getElementById('chat_desc');
		textinput.contentEditable = true;
		textinput.classList.add('editing');
		textinput.focus();
	},
	editChatDescSend() {
		var textinput = document.getElementById('chat_desc');
		if (textinput.classList.contains('editing')) {
			textinput.classList.remove('editing');
			textinput.contentEditable = false;
			textinput.innerHTML = textinput.textContent;
			if (this.selected_chat.groupchat) {
				console.log("wtf man");
			}
			else {
				this.patchContact({handle:this.selected_chat.partner,bio:textinput.textContent});
			}

		}
	},


	dragContact(event) {
		var el = event.currentTarget;
		var cid = el.dataset.chatid;
		var partner = this.chats[cid].partner;
		event.dataTransfer.setData('text/plain',partner);
	},
	dragContactReceive(event) {
		event.preventDefault();
		const contact_handle = event.dataTransfer.getData('text');
		if (contact_handle) {
			const el = event.currentTarget;
			const cid = el.dataset.chatid;
			const chat = this.chats[cid];
			console.log(chat);
			if (chat.groupchat) {
				post("/api/add_chat_member",{
					chat_uid: cid,
					partner_handle: contact_handle
				})
					.then((response) => response.json())
					.then((result=>{
						chat.partners = result.partners;
					}))
				//chat.partners[contact_handle] = this.contacts[contact_handle].name;
			}
		}

	},

	/// CONTACTS
	patchContact(data) {
		patch("/api/contact",data)
			.then(response=>response.json())
			.then(result=>{
				this.contacts[data.handle] = result;
				for (var chat of Object.values(this.chats)) {
					if (chat.partner == data.handle) {
						chat.name = result.name;
						chat.desc = result.bio;
					}
				}
			})
	},
	addFriend(handle){
		this.patchContact({handle:handle,friend:true});
	},
	removeFriend(handle) {
		this.patchContact({handle:handle,friend:false});
	},

	// MESSAGES
	patchMessage(data) {
		patch("/api/message",data)
			.then(response=>response.json())
			.then(result=>{
				for (var chat of Object.values(this.chats)) {
					var i = chat.messages?.length;
					while(i--) {
						if (chat.messages[i].uid == data.uid) {
							chat.messages[i] = result;
							if (chat.messages) { chat.latest_message = chat.messages.slice(-1)[0] }
							break;
						}
					}
				}
			})
	},
	editMessageSend(msg_uid){
		var element = document.getElementById('message_' + msg_uid);
		var textinput = element.getElementsByClassName('message_text')[0];
		if (textinput.classList.contains('editing')) {
			textinput.classList.remove('editing');
			textinput.contentEditable = false;
			this.patchMessage({uid:msg_uid,content:this.html_to_markdown(textinput.innerHTML)})
		}
	},
	editMessage(msg_uid) {
		var element = document.getElementById('message_' + msg_uid);
		var textinput = element.getElementsByClassName('message_text')[0];
		textinput.contentEditable = true;
		textinput.classList.add('editing');
		textinput.focus();
	},
	deleteMessage(msg_uid) {
		del("/api/message",{
				uid:msg_uid
		})
			.then(result=>{
				for (var chat of Object.values(this.chats)) {
					var i = chat.messages?.length;
					while(i--) {
						if (chat.messages[i].uid == msg_uid) {
							chat.messages.splice(i,1);
							break;
						}
					}
					if (chat.messages) { chat.latest_message = chat.messages.slice(-1)[0] }
				}
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
						this.selected_chat.messages[i].content = result.content;
						this.selected_chat.messages[i].display_simplified = result.display_simplified;
						break;
					}
				}
				this.chats[this.selected_chat.uid].latest_message = this.selected_chat.messages.slice(-1)[0];
			})
	},

	sendMessageMedia(event) {
		event.preventDefault();
		var chatwindow = document.getElementById('chat');
		chatwindow.style.backgroundColor='';

		var atEnd = ((chatwindow.scrollTop + 2000) > chatwindow.scrollHeight);
		var uid = this.selected_chat.uid;

		const file = event.dataTransfer.files[0];
		if (file) {
			const formData = new FormData();
			formData.append('file', file);
			fetch('/api/upload_media', {
		      method: 'POST',
		      body: formData,
		    })
		    .then((response) => response.json())
		    .then((result) => {
					this.sendMessage("",result.path);

		    })
		}

	},


	deleteChat(chat_uid) {
		del("/api/chat",{
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
	usermatch_regex: /@(\S*$)/gi,
	html_to_markdown(html) {
		html = DOMPurify.sanitize(html, {ALLOWED_TAGS:['b','i','strong','li','ol','p','h1','h2','h3','h4']});
		return converter.makeMarkdown(html);
	},
	markdown_to_html(markdown) {
		return converter.makeHtml(markdown);
	},
	getEmojis() {
		const seg = new Intl.Segmenter();
		const segments = [...seg.segment(this.userinfo.preferred_emojis)]
		return segments.map(x=>x.segment);
	}
}


function getAppData() {
	return window.appdata;
}
