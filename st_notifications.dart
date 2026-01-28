import 'package:app/st_dashboard.dart';
import 'package:flutter/material.dart';
import 'st_sidemenu.dart';
import 'st_chat_screen.dart';

class STNotificationsScreen extends StatelessWidget {
  const STNotificationsScreen({super.key});

  // Sample notification data
  final List<Map<String, String>> _notifications = const [
    {
      "title": "Assignment Submitted",
      "subtitle": "Your assignment has been successfully submitted.",
      "time": "2 hrs ago",
    },
    {
      "title": "Fee Payment Reminder",
      "subtitle": "Your fee payment is due tomorrow.",
      "time": "1 day ago",
    },
    {
      "title": "Transport Update",
      "subtitle": "Bus will arrive 10 minutes late today.",
      "time": "Yesterday",
    },
  ];

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
                colors: [Color(0xFF025061), Color(0xFF045981)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
          ),
          elevation: 0,
          title: Row(
            children: [
              // Menu Icon
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
              // Logo
              Image.asset('assets/logo.png', height: 40),
            ],
          ),
        ),
      ),

      // -------- Body --------
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _notifications.length,
        itemBuilder: (context, index) {
          final notif = _notifications[index];
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
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
                const Icon(
                  Icons.notifications,
                  color: Color(0xFF025061),
                  size: 28,
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        notif["title"]!,
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        notif["subtitle"]!,
                        style: const TextStyle(
                          fontSize: 13,
                          color: Colors.grey,
                        ),
                      ),
                    ],
                  ),
                ),
                Text(
                  notif["time"]!,
                  style: const TextStyle(fontSize: 11, color: Colors.grey),
                ),
              ],
            ),
          );
        },
      ),

      // -------- Bottom Navigation Bar --------
      bottomNavigationBar: Container(
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
            currentIndex: 2, // Notifications = 2
            elevation: 0,
            backgroundColor: Colors.transparent,
            selectedItemColor: Colors.white,
            unselectedItemColor: Colors.white70,
            onTap: (index) {
              if (index == 0) {
                // Home
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => const StudentDashboard(),
                  ),
                );
              } else if (index == 1) {
                // Chat
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => const STChatScreen()),
                );
              }
            },
            items: const [
              BottomNavigationBarItem(icon: Icon(Icons.home), label: "Home"),
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
    );
  }
}
