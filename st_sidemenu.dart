import 'package:app/st_assignment.dart';
import 'package:app/st_attendance.dart';
import 'package:app/st_classProgress.dart';
import 'package:app/st_examination.dart';
import 'package:app/st_feedback.dart';
import 'package:app/st_feepayment.dart';
import 'package:app/st_profile.dart';
import 'package:app/st_timetable.dart';
import 'package:app/st_transport.dart';
import 'package:flutter/material.dart';
import 'onboarding_screen.dart'; // Make sure this file exists

class STSideMenu extends StatelessWidget {
  const STSideMenu({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),
      appBar: AppBar(
        backgroundColor: const Color(0xFF025061),
        title: const Text("Menu"),
        automaticallyImplyLeading: true, // Back button
        actions: [
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white),
            onPressed: () {
              // Navigate to OnboardingScreen
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(
                  builder: (context) => const OnboardingScreen(),
                ),
                (route) => false,
              );
            },
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // -------- User Info Card --------
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.05),
                    blurRadius: 15,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Row(
                children: [
                  const CircleAvatar(
                    radius: 30,
                    backgroundImage: AssetImage(
                      "assets/profile.png",
                    ), // placeholder
                  ),
                  const SizedBox(width: 16),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
                      Text(
                        "Student Name",
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        "Class / Roll No",
                        style: TextStyle(fontSize: 14, color: Colors.grey),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 30),

            // -------- Menu Items with card effect --------
            Expanded(
              child: ListView(
                children: [
                  _MenuItemCard(
                    icon: Icons.person,
                    title: "Profile",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const StProfileScreen(),
                        ),
                      );
                    },
                  ),
                  _MenuItemCard(
                    icon: Icons.calendar_today,
                    title: "Attendance",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const StAttendance(),
                        ),
                      );
                    },
                  ),
                  _MenuItemCard(
                    icon: Icons.schedule,
                    title: "Timetable",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => StudentTimetablePage(),
                        ),
                      );
                    },
                  ),
                  _MenuItemCard(
                    icon: Icons.payment,
                    title: "Fee Payment",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const StFeePayment(),
                        ),
                      );
                    },
                  ),
                  _MenuItemCard(
                    icon: Icons.assignment,
                    title: "Assignments",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(builder: (context) => StAssignment()),
                      );
                    },
                  ),

                  // ✅ NEW ITEMS ADDED
                  _MenuItemCard(
                    icon: Icons.edit_document,
                    title: "Examination",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const StudentExaminationPage(),
                        ),
                      );
                    },
                  ),
                  _MenuItemCard(
                    icon: Icons.directions_bus,
                    title: "Transport Tracking",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const StTransportScreen(),
                        ),
                      );
                    },
                  ),
                  _MenuItemCard(
                    icon: Icons.trending_up,
                    title: "Class Progress",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const StClassProgress(),
                        ),
                      );
                    },
                  ),

                  _MenuItemCard(
                    icon: Icons.feedback,
                    title: "Feedback",
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const StFeedbackScreen(),
                        ),
                      );
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ===== Menu Item Card =====
class _MenuItemCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;

  const _MenuItemCard({
    required this.icon,
    required this.title,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: ListTile(
        leading: Icon(icon, color: const Color(0xFF025061)),
        title: Text(
          title,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
        ),
        trailing: const Icon(
          Icons.arrow_forward_ios,
          size: 16,
          color: Colors.grey,
        ),
        onTap: onTap,
      ),
    );
  }
}
