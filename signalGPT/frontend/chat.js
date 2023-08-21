
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
		this.selected_chat.messages.push(msg);
		this.chats[this.selected_chat.uid].latest_message = msg;

		if (atEnd) {
			this.$nextTick(()=>{
				chatwindow.scrollTop = chatwindow.scrollHeight;
			});

		}
		fetch("/api/send_message",{
			method:"POST",
			headers: {
				'Content-Type': 'application/json'
			},
			body:JSON.stringify({
				chat_id: this.selected_chat.uid,
				content: content,
				timestamp: timestamp
			})
		})
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
	chatInput(event) {
		var inputfield = document.getElementById('chat_input').children[0];
		var content = inputfield.value;
		if (event.code == "Enter") {

			if (content == "") {
				this.requestResponse();
			}
			else {
				inputfield.value = "";
				this.sendMessage(content);
			}

		}

		this.updateCurrentInput(content);
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
	manual_update:0,
	current_input: "",
	usermatch_regex: /@(\S*$)/g,
	mkdw: new showdown.Converter()
}


function getAppData() {
	return window.appdata;
}
