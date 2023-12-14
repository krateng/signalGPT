
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

window.onpopstate = function(event) {
  if (!event.state || !event.state.chatOpened) {
    // User pressed back, remove your class to hide the chat
    document.getElementById('app').classList.remove('chat_selected');
  }
};

window.appdata = {
	chats:{},
	contacts:{},
	selected_chat:null,
	selected_newchar_male:false,
	selected_model_advanced:false,
	selectChat(uid){
			if (this.chats[uid]?.full_loaded) {
				this.selected_chat = this.chats[uid];
				var chatwindow = document.getElementById('chat');
				var root = document.getElementById('app');
				root.classList.add('chat_selected');
				history.pushState({ chatOpened: uid }, '', window.location.href.split('?')[0] + "?chat=" + uid);

				this.$nextTick(()=>{
					chatwindow.scrollTop = chatwindow.scrollHeight;
				});
			}
			else {
				this.getChat(uid)
		    	.then(result=>{
		    		this.selectChat(uid);
		    	});
			}

	},
	async getData(){
		await fetch("/api/data")
			.then(response=>response.json())
			.then(result=>{
				this.chats = result.chats;
				this.contacts = result.contacts;
				this.userinfo = result.userinfo;
				this.resolveReferences(this.chats);
				this.resolveReferences(this.contacts);
			});

	},
	resolveReferences(obj) {

		for (var key of Object.keys(obj)) {
			if (typeof obj[key] === 'object' && obj[key] !== null) {
				if (obj[key].hasOwnProperty("ref")) {
					var ref_type = obj[key]['ref'];
					var ref_key = obj[key]['key'];
					var entity = this[ref_type][ref_key];

					if (!entity) {
						var funcs = {
							chats:this.getChat,
							contacts:this.getContact
						}
						console.log('missing reference:',ref_type,ref_key);
						let key_to_save_in = key;
						funcs[ref_type].bind(this)(ref_key)
							.then(result=>{
								obj[key_to_save_in] = this[ref_type][ref_key];
								this.resolveReferences(obj[key_to_save_in]);
								this.manual_update++;
							});

					}
					else {
						obj[key] = entity;
					}

				}
				else {
					this.resolveReferences(obj[key]);
				}
			}
		}
	},

	sendMessage(content,media,messagetype) {

		var chatwindow = document.getElementById('chat');
		var atEnd = ((chatwindow.scrollTop + 2000) > chatwindow.scrollHeight);

		var timestamp = Math.floor(Date.now() / 1000);

		post("/api/send_message",{
				chat_id: this.selected_chat.uid,
				content: media ? media : content,
				messagetype: messagetype,
				timestamp: timestamp
			})
				.then(response=>response.json())
				.then(result=>{
					console.log(result);
					this.selected_chat.messages.push(result);
					this.chats[this.selected_chat.uid].latest_message = this.selected_chat.messages.slice(-1)[0];
					if (atEnd || true) { //always scroll down
						this.$nextTick(()=>{
							chatwindow.scrollTop = chatwindow.scrollHeight;
						});

					}
				});
	},

	requestResponse(force_user=null) {

		var chatwindow = document.getElementById('chat');
		var atEnd = ((chatwindow.scrollTop + 2000) > chatwindow.scrollHeight);

		post("/api/guess_next_responder",{
			chat_id:this.selected_chat.uid,
			force_user_handle: force_user
		})
			.then(response=>response.json())
			.then(result=>{
				var pseudomsg = {
					author:result,
					message_type: "Pseudo",
					currently_typing: true,
					timestamp: new Date().getTime() / 1000,
					content: ""
				}
				this.selected_chat.messages.push(pseudomsg);

				if (atEnd) {
					this.$nextTick(()=>{
						chatwindow.scrollTop = chatwindow.scrollHeight;
					});

				}

				post("/api/generate_message",{
					chat_id:this.selected_chat.uid,
					bettermodel:this.selected_model_advanced,
					responder_handle: result.handle
				})
					.then(response=>response.json())
					.then(result=>{
						this.selected_chat.messages.pop();
						for (var msg of result.messages) {
							this.selected_chat.messages.push(msg);
							this.resolveReferences(msg);
							this.chats[this.selected_chat.uid].latest_message = msg;
							if (msg.message_type.includes("Meta")) {
								this.getChat(this.selected_chat.uid);
							}
							if (atEnd) {
								this.$nextTick(()=>{
									chatwindow.scrollTop = chatwindow.scrollHeight;
								});

							}
						}

					})
					.catch(error=>{
							this.selected_chat.messages.pop();
					});

			});

		return;


	},
	startEdit(event) {
		var element = document.getElementById(event.currentTarget.dataset.edittarget);
		element.contentEditable = true;
		element.classList.add('editing');
		element.focus();

	},
	finishEdit(event,func) {
		var element = event.currentTarget;
		if (element.classList.contains('editing')) {
			element.classList.remove('editing');
			element.contentEditable = false;
			if (element.dataset.nohtml) {
				element.innerHTML = element.innerText;
			}
			var key = element.dataset.entitykey;
			console.log('calling',func,'with',element.innerHTML,key);
			func.bind(this)(key,element.innerHTML);
		}

	},
	findNewContact(searchstr) {
		post("/api/contact",{
			desc:searchstr
			//male:this.selected_newchar_male
		})
			.then(response=>response.json())
			.then(result=>{
				this.contacts[result.handle] = result;
				this.resolveReferences(result);
			})
	},
	submitMessageFromInput() {
	    var element = document.getElementById("chat_input_field");
	    this.sendMessage(element.value,null);
       	element.value = "";
	},
	keyboardInput(event) {
		var element = event.target;
		if (element.id == "chat_input_field") {
			if (event.which == 13 && !event.shiftKey) {
				if (element.value == "") {
					this.requestResponse();
				}
				else {
					this.submitMessageFromInput();

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
	getChat(uid) {
		return fetch("/api/chat/" + uid)
			.then(response=>response.json())
			.then(result=>{
				console.log(result);
				this.chats[result.uid] = this.chats[result.uid] ?? {};
				Object.assign(this.chats[result.uid],result);
				this.chats[result.uid].full_loaded = true;
				this.resolveReferences(this.chats[uid]);

			})
	},
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
				Object.assign(this.chats[result.uid],result);
				this.resolveReferences(this.chats[result.uid]);
				this.selected_chat = this.chats[result.uid];
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
						this.patchContact({handle:this.chats[uid].partner.handle,image:result.path});
					}

		    })
		}

	},
	alterChatName(uid,name) {
		var chat = this.chats[uid];
		if (chat.groupchat) {
			this.patchChat({uid:uid,name:name});
		}
		else {
			this.patchContact({handle:chat.partner.handle,name:name});
		}

	},



	dragContact(event) {
		var el = event.currentTarget;
		var cid = el.dataset.chatid;
		var partner = this.chats[cid].partner.handle;
		event.dataTransfer.setData('text/plain',partner);
	},
	dragContactReceive(event) {
		event.preventDefault();
		const contact_handle = event.dataTransfer.getData('text');
		if (contact_handle) {
			const el = event.currentTarget;
			const cid = el.dataset.chatid;
			const chat = this.chats[cid];
			if (chat.groupchat) {
				post("/api/add_chat_member",{
					chat_uid: cid,
					partner_handle: contact_handle
				})
					.then((response) => response.json())
					.then((result=>{
						Object.assign(chat,result);
						this.resolveReferences(chat);
					}))
				//chat.partners[contact_handle] = this.contacts[contact_handle].name;
			}
		}

	},

	/// CONTACTS
	getContact(handle) {
		return fetch("/api/contact/" + handle)
			.then(response=>response.json())
			.then(result=>{
				console.log(result);
				this.contacts[result.handle] = this.contacts[result.handle] ?? {};
				Object.assign(this.contacts[result.handle],result);
				this.resolveReferences(this.contacts[handle]);

			})
	},
	patchContact(data) {
		return patch("/api/contact",data)
			.then(response=>response.json())
			.then(result=>{
				Object.assign(this.contacts[data.handle],result);
				this.resolveReferences(this.contacts[data.handle]);
			})
	},
	addFriend(handle){
		this.patchContact({handle:handle,friend:true});
	},
	removeFriend(handle) {
		this.patchContact({handle:handle,friend:false});
	},
	startChat(handle) {
		for (var chat of Object.values(this.chats)) {
			if (chat.partner?.handle == handle) {
				this.selectChat(chat.uid);
				return;
			}
		}

		this.patchContact({handle:handle,start_chat:true})
			.then(result=>{
				this.$nextTick(()=>{
					this.selectChat(this.contacts[handle].direct_chat.uid);
				});

			})
	},
	alterContactBio(handle,text) {
		var contact = this.contacts[handle];
		this.patchContact({handle:handle,bio:text});
	},

	// MESSAGES
	patchMessage(data) {
		patch("/api/message",data)
			.then(response=>response.json())
			.then(result=>{
				this.resolveReferences(result);
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
	alterMessageText(uid,text){
		this.patchMessage({uid:uid,content:this.html_to_markdown(text)});
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

		var i = this.selected_chat.messages.length;
		while(i--) {
			if (this.selected_chat.messages[i].uid == msg_uid) {
				this.selected_chat.messages[i].regenerating = true;
			}
		}

		post("/api/regenerate_message",{
			uid:msg_uid,
			bettermodel:this.selected_model_advanced
		})
			.then(response=>response.json())
			.then(result=>{
				var i = this.selected_chat.messages.length;
				while(i--) {
					if (this.selected_chat.messages[i].uid == msg_uid) {
						// just so this doesn't get overwritten by the yet-to-be-resolved-reference
						result.author = this.selected_chat.messages[i].author;
						Object.assign(this.selected_chat.messages[i],result);
						this.selected_chat.messages[i].regenerating = false;
						//this.selected_chat.messages[i].content = result.content;
						//this.selected_chat.messages[i].display_simplified = result.display_simplified;
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
			var mediatype = file.type.split('/')[0];
			const formData = new FormData();
			formData.append('file', file);
			fetch('/api/upload_media', {
		      method: 'POST',
		      body: formData,
		    })
		    .then((response) => response.json())
		    .then((result) => {
					this.sendMessage("",result.path,mediatype);

		    })
		}

	},

	changeAuthor(msg_uid) {
		for (var chat of Object.values(this.chats)) {
			var i = chat.messages?.length;
			while(i--) {
				if (chat.messages[i].uid == msg_uid) {
					var msg = chat.messages[i];
					var participants = [this.userinfo.handle];
					if (chat.groupchat) {
						participants = participants.concat(chat.partners.map(x=>x.handle));
					}
					else {
						participants.push(chat.partner.handle);
					}
					console.log(participants);
					var j = participants.length;
					var pickNext = false;
					var overflows_allowed = 1;
					while (j-- || overflows_allowed--) {
						if (j<0) {
							j = participants.length-1;
						}
						if (pickNext) {
							if (participants[j] == this.userinfo.handle) {
								this.patchMessage({uid:msg_uid,author_handle:null})
							}
							else {
								this.patchMessage({uid:msg_uid,author_handle:participants[j]});
							}

							break;
						}
						if ((msg.author?.handle || this.userinfo.handle) == participants[j]) {
							pickNext = true;
						}
					}
				}
			}
		}
	},


	deleteChat(chat_uid) {
		del("/api/chat",{
				uid:chat_uid
		})
			.then(result=>{
				delete this.chats[chat_uid];
				if (this.selected_chat.uid == chat_uid) {
					this.selected_chat = null;
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
