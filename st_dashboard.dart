import 'package:app/st_assignment.dart';
import 'package:app/st_classProgress.dart';
import 'package:app/st_doucemnt.dart';
import 'package:app/st_event.dart';
import 'package:app/st_examination.dart';
import 'package:app/st_feedback.dart';
import 'package:app/st_feepayment.dart';
import 'package:app/st_notifications.dart';
import 'package:app/st_teachers.dart';
import 'package:app/st_timetable.dart';
import 'package:app/st_transport.dart';
import 'package:flutter/material.dart';
import 'st_sidemenu.dart';
import 'st_chat_screen.dart';
import 'st_attendance.dart';

class StudentDashboard extends StatefulWidget {
  const StudentDashboard({super.key});

  @override
  State<StudentDashboard> createState() => _StudentDashboardState();
}

class _StudentDashboardState extends State<StudentDashboard> {
  final TextEditingController searchController = TextEditingController();
  String searchQuery = "";
  final List<Map<String, dynamic>> services = [
    {
      "title": "Attendance",
      "icon": Icons.calendar_today,
      "screen": const StAttendance(),
    },
    {
      "title": "Timetable",
      "icon": Icons.schedule,
      "screen": StudentTimetablePage(),
    },
    {
      "title": "Examination",
      "icon": Icons.edit_document,
      "screen": StudentExaminationPage(),
    },
    {
      "title": "Assignments",
      "icon": Icons.assignment,
      "screen": StAssignment(),
    },
    {"title": "Documents", "icon": Icons.folder, "screen": StDocumentScreen()},
    {"title": "Teachers", "icon": Icons.school, "screen": StTeacher()},
    {"title": "Fees Payment", "icon": Icons.payment, "screen": StFeePayment()},
    {"title": "Events", "icon": Icons.event_sharp, "screen": StEventScreen()},
    {
      "title": "Class Progress",
      "icon": Icons.trending_up,
      "screen": StClassProgress(),
    },
    {
      "title": "Transport Tracking",
      "icon": Icons.bus_alert_outlined,
      "screen": StTransportScreen(),
    },
    {"title": "Feedback", "icon": Icons.feedback, "screen": StFeedbackScreen()},
  ];
  List<Map<String, dynamic>> get filteredServices {
    if (searchQuery.isEmpty) return services;

    return services.where((service) {
      return service["title"].toString().toLowerCase().contains(searchQuery);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),

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
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
          ),
          elevation: 0,
          title: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.menu, color: Colors.white),
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (context) => STSideMenu()),
                  );
                },
              ),
              const SizedBox(width: 8),
              Image.asset('assets/logo.png', height: 40),
            ],
          ),
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 16),
              child: InkWell(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const STNotificationsScreen(),
                    ),
                  );
                },
                child: const Icon(Icons.notifications, color: Colors.white),
              ),
            ),
          ],
        ),
      ),

      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                "Hello 👋",
                style: TextStyle(fontSize: 14, color: Colors.grey),
              ),
              const SizedBox(height: 4),
              const Text(
                "Student",
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF1F1F1F),
                ),
              ),
              const SizedBox(height: 20),

              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(24),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.08),
                      blurRadius: 20,
                      offset: const Offset(0, 10),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    Container(
                      height: 50,
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF4F7FB),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.search, color: Colors.grey),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: searchController,
                              onChanged: (value) {
                                setState(() {
                                  searchQuery = value.toLowerCase();
                                });
                              },
                              decoration: const InputDecoration(
                                hintText: "Search modules...",
                                border: InputBorder.none,
                              ),
                            ),
                          ),
                          if (searchQuery.isNotEmpty)
                            GestureDetector(
                              onTap: () {
                                setState(() {
                                  searchController.clear();
                                  searchQuery = "";
                                });
                              },
                              child: const Icon(
                                Icons.close,
                                color: Colors.grey,
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),

                    GridView.count(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      crossAxisCount: 2,
                      crossAxisSpacing: 16,
                      mainAxisSpacing: 16,
                      children: [
                        _PremiumCard(
                          title: "Attendance",
                          icon: Icons.calendar_today,
                          bgColor: Color(0xFFFFE5E5),
                          circleColor: Color(0xFFFFCACA),
                          onTap: () {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (context) => StAttendance(),
                              ),
                            );
                          },
                        ),
                        _PremiumCard(
                          title: "Timetable",
                          icon: Icons.schedule,
                          bgColor: Color(0xFFE6E8FF),
                          circleColor: Color(0xFFD0D5FF),
                          onTap: () {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (context) => StudentTimetablePage(),
                              ),
                            );
                          },
                        ),
                        _PremiumCard(
                          title: "Fees",
                          icon: Icons.receipt_long,
                          bgColor: Color(0xFFE5FFF4),
                          circleColor: Color(0xFFC9F5E6),
                          onTap: () {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (context) => StFeePayment(),
                              ),
                            );
                          },
                        ),
                        _PremiumCard(
                          title: "Notifications",
                          icon: Icons.notifications,
                          bgColor: Color(0xFFE6F3FF),
                          circleColor: Color(0xFFCCE6FF),
                          onTap: () {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (context) => STNotificationsScreen(),
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 30),

              const Text(
                "Student Services",
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF1F1F1F),
                ),
              ),
              const SizedBox(height: 16),

              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 4,
                  crossAxisSpacing: 16,
                  mainAxisSpacing: 20,
                ),
                itemCount: filteredServices.length,
                itemBuilder: (context, index) {
                  final service = filteredServices[index];
                  return _ServiceTile(
                    service["title"],
                    service["icon"],
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => service["screen"]),
                      );
                    },
                  );
                },
              ),

              const SizedBox(height: 40),
            ],
          ),
        ),
      ),

      // ===== Bottom Navigation Bar (ADDED ONLY) =====
      bottomNavigationBar: Padding(
        padding: const EdgeInsets.all(16),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(40),
          child: Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Color.fromARGB(255, 2, 50, 61),
                  Color.fromARGB(255, 4, 89, 129),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: BottomNavigationBar(
              currentIndex: 0,
              elevation: 0,
              backgroundColor: Colors.transparent,
              selectedItemColor: Colors.white,
              unselectedItemColor: Colors.white70,
              onTap: (index) {
                if (index == 1) {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const STChatScreen(),
                    ),
                  );
                } else if (index == 2) {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const STNotificationsScreen(),
                    ),
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
      ),
    );
  }
}

// ===== Premium Card =====
class _PremiumCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color bgColor;
  final Color circleColor;
  final VoidCallback? onTap;

  const _PremiumCard({
    required this.title,
    required this.icon,
    required this.bgColor,
    required this.circleColor,
    this.onTap, // ✅ optional
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
          const Spacer(),
          Icon(icon, size: 28, color: const Color(0xFF5BA9F9)),
        ],
      ),
    );
  }
}

// ===== Service Tile =====
class _ServiceTile extends StatelessWidget {
  final String title;
  final IconData icon;
  final VoidCallback? onTap;

  const _ServiceTile(this.title, this.icon, {this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Icon(icon, color: const Color(0xFF5BA9F9), size: 24),
          ),
          const SizedBox(height: 6),
          Text(
            title,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w500),
          ),
        ],
      ),
    );
  }
}
