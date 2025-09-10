document.addEventListener('DOMContentLoaded', () => {
    const conversationList = document.getElementById('conversation-list');
    const messageList = document.getElementById('message-list');
    const conversationSubject = document.getElementById('conversation-subject');
    const messageInput = document.getElementById('message-body');
    const sendButton = document.getElementById('send-button');

    let selectedConversationId = null;

    // Fetch all conversations and populate the sidebar
    fetch('/api/conversations')
        .then(response => response.json())
        .then(conversations => {
            conversations.forEach(conversation => {
                const li = document.createElement('li');
                li.textContent = conversation.subject;
                li.dataset.id = conversation.id;
                li.addEventListener('click', () => {
                    selectConversation(conversation.id, conversation.subject);
                });
                conversationList.appendChild(li);
            });
        });

    // Function to select a conversation and fetch its messages
    function selectConversation(id, subject) {
        selectedConversationId = id;
        conversationSubject.textContent = subject;
        messageList.innerHTML = ''; // Clear previous messages

        // Highlight the selected conversation
        Array.from(conversationList.children).forEach(li => {
            li.classList.toggle('active', li.dataset.id == id);
        });

        fetch(`/api/conversations/${id}`)
            .then(response => response.json())
            .then(messages => {
                messages.forEach(message => {
                    const messageDiv = document.createElement('div');
                    messageDiv.classList.add('message');
                    messageDiv.innerHTML = `
                        <div class="sender">${message.sender_type} (${message.sender_id})</div>
                        <div class="body">${message.body}</div>
                    `;
                    messageList.appendChild(messageDiv);
                });
                // Scroll to the bottom of the message list
                messageList.scrollTop = messageList.scrollHeight;
            });
    }

    // Send a new message
    sendButton.addEventListener('click', () => {
        const body = messageInput.value;
        if (!body || !selectedConversationId) {
            return;
        }

        fetch(`/api/conversations/${selectedConversationId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ body: body })
        })
        .then(response => response.json())
        .then(newMessage => {
            messageInput.value = '';
            // Refresh the message list
            selectConversation(selectedConversationId, conversationSubject.textContent);
        });
    });
});
