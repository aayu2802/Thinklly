import 'package:app/st_notifications.dart';
import 'package:app/st_sidemenu.dart';
import 'package:flutter/material.dart';
import 'st_single_chat_screen.dart';

class STChatScreen extends StatefulWidget {
  const STChatScreen({super.key});

  @override
  State<STChatScreen> createState() => _STChatScreenState();
}

class _STChatScreenState extends State<STChatScreen> {
  final TextEditingController _searchController = TextEditingController();

  final List<Map<String, dynamic>> _allChats = [
    {
      "name": "Class Teacher",
      "message": "Please submit your assignment.",
      "time": "09:30 AM",
      "unread": true,
    },
    {
      "name": "Admin Office",
      "message": "Fee payment received.",
      "time": "Yesterday",
      "unread": false,
    },
    {
      "name": "Transport Dept",
      "message": "Bus will arrive 10 min late.",
      "time": "Mon",
      "unread": false,
    },
  ];

  List<Map<String, dynamic>> _filteredChats = [];

  @override
  void initState() {
    super.initState();
    _filteredChats = _allChats;
  }

  void _searchChat(String query) {
    setState(() {
      _filteredChats = _allChats
          .where(
            (chat) => chat["name"].toLowerCase().contains(query.toLowerCase()),
          )
          .toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),

      // -------- AppBar --------
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(60),
        child: AppBar(
          automaticallyImplyLeading: false,
          flexibleSpace: Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Color.fromARGB(255, 2, 50, 61),
                  Color.fromARGB(255, 4, 89, 129),
                ],
              ),
            ),
          ),
          title: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.menu, color: Colors.white),
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const STSideMenu()),
                  );
                },
              ),
              const SizedBox(width: 8),
              Image.asset('assets/logo.png', height: 40),
            ],
          ),
        ),
      ),

      body: Column(
        children: [
          // -------- Search Bar --------
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchController,
              onChanged: _searchChat,
              decoration: InputDecoration(
                hintText: "Search chats...",
                prefixIcon: const Icon(Icons.search),
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(18),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),

          // -------- Chat List --------
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _filteredChats.length,
              itemBuilder: (context, index) {
                final chat = _filteredChats[index];

                return GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => STSingleChatScreen(name: chat["name"]),
                      ),
                    );
                  },
                  child: _ChatTile(
                    name: chat["name"],
                    lastMessage: chat["message"],
                    time: chat["time"],
                    unread: chat["unread"],
                  ),
                );
              },
            ),
          ),
        ],
      ),

      // -------- Bottom Nav --------
      bottomNavigationBar: Container(
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Color.fromARGB(255, 2, 50, 61),
              Color.fromARGB(255, 4, 89, 129),
            ],
          ),
          borderRadius: BorderRadius.all(Radius.circular(30)),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(30),
          child: Container(
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF025061), Color(0xFF045981)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.all(Radius.circular(30)),
            ),
            child: ClipRRect(
              borderRadius: const BorderRadius.all(Radius.circular(30)),
              child: BottomNavigationBar(
                currentIndex: 1, // Chat = 1
                backgroundColor: Colors.transparent,
                elevation: 0,
                selectedItemColor: Colors.white,
                unselectedItemColor: Colors.white70,
                onTap: (index) {
                  if (index == 0) {
                    // Navigate to Home
                    Navigator.pop(context);
                  } else if (index == 1) {
                    // Stay on Chat (current page)
                  } else if (index == 2) {
                    // Navigate to Notifications
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => const STNotificationsScreen(),
                      ),
                    );
                  }
                },
                items: const [
                  BottomNavigationBarItem(
                    icon: Icon(Icons.home),
                    label: "Home",
                  ),
                  BottomNavigationBarItem(
                    icon: Icon(Icons.chat_sharp),
                    label: "Chat",
                  ),
                  BottomNavigationBarItem(
                    icon: Icon(Icons.notifications),
                    label: "Alerts",
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// -------- Chat Tile --------
class _ChatTile extends StatelessWidget {
  final String name;
  final String lastMessage;
  final String time;
  final bool unread;

  const _ChatTile({
    required this.name,
    required this.lastMessage,
    required this.time,
    required this.unread,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 22,
            backgroundColor: const Color(0xFF025061),
            child: Text(
              name[0],
              style: const TextStyle(color: Colors.white, fontSize: 18),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  lastMessage,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.grey, fontSize: 13),
                ),
              ],
            ),
          ),
          Column(
            children: [
              Text(
                time,
                style: const TextStyle(fontSize: 11, color: Colors.grey),
              ),
              if (unread)
                const Padding(
                  padding: EdgeInsets.only(top: 6),
                  child: CircleAvatar(radius: 4, backgroundColor: Colors.red),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
