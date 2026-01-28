import 'package:flutter/material.dart';

class StAttendance extends StatefulWidget {
  const StAttendance({super.key});

  @override
  State<StAttendance> createState() => _StAttendanceState();
}

class _StAttendanceState extends State<StAttendance> {
  // Current month data (dummy for example)
  final List<Map<String, String>> attendanceData = [
    {"date": "01 Jan", "status": "Present"},
    {"date": "02 Jan", "status": "Absent"},
    {"date": "03 Jan", "status": "Present"},
    {"date": "04 Jan", "status": "Leave"},
    {"date": "05 Jan", "status": "Present"},
    {"date": "06 Jan", "status": "Present"},
    {"date": "07 Jan", "status": "Absent"},
  ];

  final Color darkTeal = const Color.fromARGB(255, 2, 50, 61);
  final Color blueTeal = const Color.fromARGB(255, 4, 89, 129);

  @override
  Widget build(BuildContext context) {
    int totalDays = attendanceData.length;
    int presentDays = attendanceData
        .where((d) => d["status"] == "Present")
        .length;
    int absentDays = attendanceData
        .where((d) => d["status"] == "Absent")
        .length;
    int leaveDays = attendanceData.where((d) => d["status"] == "Leave").length;

    double attendancePercentage = totalDays == 0
        ? 0
        : (presentDays / totalDays) * 100;

    return Scaffold(
      appBar: AppBar(
        centerTitle: true,
        elevation: 0,
        title: const Text(
          "Attendance",
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        flexibleSpace: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [darkTeal, blueTeal]),
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 🔹 Summary Cards
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _summaryCard("Present", presentDays, Colors.green),
                _summaryCard("Absent", absentDays, Colors.redAccent),
                _summaryCard("Leave", leaveDays, Colors.orange),
              ],
            ),

            const SizedBox(height: 26),

            // 🔹 Attendance Percentage
            Center(
              child: Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.08),
                      blurRadius: 14,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox(
                      width: 130,
                      height: 130,
                      child: CircularProgressIndicator(
                        value: attendancePercentage / 100,
                        strokeWidth: 10,
                        backgroundColor: Colors.grey.shade300,
                        valueColor: const AlwaysStoppedAnimation(Colors.green),
                      ),
                    ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          "${attendancePercentage.toStringAsFixed(1)}%",
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          "Attendance",
                          style: TextStyle(fontSize: 12, color: Colors.black54),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 26),

            const Text(
              "Daily Attendance",
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 12),

            // 🔹 Daily List
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: attendanceData.length,
              itemBuilder: (context, index) {
                final day = attendanceData[index];
                Color statusColor;

                switch (day["status"]) {
                  case "Present":
                    statusColor = Colors.green;
                    break;
                  case "Absent":
                    statusColor = Colors.redAccent;
                    break;
                  case "Leave":
                    statusColor = Colors.orange;
                    break;
                  default:
                    statusColor = Colors.grey;
                }

                return Container(
                  margin: const EdgeInsets.only(bottom: 10),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.06),
                        blurRadius: 10,
                        offset: const Offset(0, 5),
                      ),
                    ],
                  ),
                  child: ListTile(
                    leading: CircleAvatar(
                      radius: 8,
                      backgroundColor: statusColor,
                    ),
                    title: Text(
                      day["date"]!,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    trailing: Text(
                      day["status"]!,
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: statusColor,
                      ),
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _summaryCard(String title, int count, Color color) {
    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.08),
              blurRadius: 12,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Column(
          children: [
            Text(
              count.toString(),
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            const SizedBox(height: 6),
            Text(title, style: const TextStyle(color: Colors.black54)),
          ],
        ),
      ),
    );
  }
}
