import 'package:flutter/material.dart';

class StudentTimetablePage extends StatelessWidget {
  const StudentTimetablePage({super.key});

  static const Color blue = Color(0xFF1E5EFF);
  static const Color green = Color(0xFF00C897);
  static const Color bg = Color(0xFFF6F8FC);

  static const List<String> days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];

  static const Map<String, List<Map<String, String>>> timetableData = {
    'Mon': [
      {
        'time': '09:00-10:00',
        'subject': 'Mathematics',
        'teacher': 'Mr. Sharma',
      },
      {'time': '10:00-11:00', 'subject': 'Physics', 'teacher': 'Ms. Verma'},
    ],
    'Tue': [
      {'time': '09:00-10:00', 'subject': 'Chemistry', 'teacher': 'Mr. Singh'},
      {'time': '10:00-11:00', 'subject': 'Maths', 'teacher': 'Mr. Sharma'},
    ],
    'Wed': [
      {'time': '09:00-10:00', 'subject': 'Biology', 'teacher': 'Ms. Roy'},
    ],
    'Thu': [
      {'time': '09:00-10:00', 'subject': 'Physics', 'teacher': 'Ms. Verma'},
      {'time': '10:00-11:00', 'subject': 'Computer', 'teacher': 'Mr. Mehta'},
    ],
    'Fri': [
      {'time': '09:00-10:00', 'subject': 'Maths', 'teacher': 'Mr. Sharma'},
    ],
  };

  bool _isCurrentClass(String day, String timeRange) {
    final now = DateTime.now();

    final currentDay = [
      'Mon',
      'Tue',
      'Wed',
      'Thu',
      'Fri',
      'Sat',
      'Sun',
    ][now.weekday - 1];

    if (day != currentDay) return false;

    final parts = timeRange.split('-');
    final start = _toTime(parts[0], now);
    final end = _toTime(parts[1], now);

    return now.isAfter(start) && now.isBefore(end);
  }

  DateTime _toTime(String t, DateTime now) {
    final parts = t.split(':');
    return DateTime(
      now.year,
      now.month,
      now.day,
      int.parse(parts[0]),
      int.parse(parts[1]),
    );
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: days.length,
      child: Scaffold(
        backgroundColor: bg,
        appBar: AppBar(
          elevation: 0,
          title: const Text(
            'Timetable',
            style: TextStyle(fontWeight: FontWeight.w600, color: Colors.white),
          ),
          centerTitle: true,
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
          bottom: TabBar(
            indicatorColor: Colors.white,
            indicatorWeight: 3,
            tabs: days.map((d) => Tab(text: d)).toList(),
          ),
        ),
        body: TabBarView(
          children: days.map((day) {
            final classes = timetableData[day] ?? [];

            return ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: classes.length,
              itemBuilder: (context, index) {
                final item = classes[index];
                final isLive = _isCurrentClass(day, item['time']!);

                return _ModernClassCard(
                  time: item['time']!,
                  subject: item['subject']!,
                  teacher: item['teacher']!,
                  isOngoing: isLive,
                );
              },
            );
          }).toList(),
        ),
      ),
    );
  }
}

class _ModernClassCard extends StatelessWidget {
  final String time;
  final String subject;
  final String teacher;
  final bool isOngoing;

  const _ModernClassCard({
    required this.time,
    required this.subject,
    required this.teacher,
    required this.isOngoing,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          /// Timeline
          Column(
            children: [
              Container(
                width: 14,
                height: 14,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: isOngoing
                      ? const LinearGradient(
                          colors: [
                            StudentTimetablePage.green,
                            StudentTimetablePage.blue,
                          ],
                        )
                      : null,
                  color: isOngoing ? null : Colors.grey.shade300,
                ),
              ),
              Container(
                width: 2,
                height: 90,
                color: Colors.grey.withOpacity(0.3),
              ),
            ],
          ),
          const SizedBox(width: 16),

          /// Card
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(18),
                color: Colors.white,
                border: isOngoing
                    ? Border.all(color: StudentTimetablePage.green, width: 1.5)
                    : null,
                boxShadow: [
                  BoxShadow(
                    color: isOngoing
                        ? StudentTimetablePage.green.withOpacity(0.25)
                        : StudentTimetablePage.blue.withOpacity(0.08),
                    blurRadius: isOngoing ? 25 : 18,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _TimePill(time),
                      const Spacer(),
                      if (isOngoing)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(20),
                            gradient: const LinearGradient(
                              colors: [
                                StudentTimetablePage.green,
                                StudentTimetablePage.blue,
                              ],
                            ),
                          ),
                          child: const Text(
                            'ONGOING',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Text(
                    subject,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    teacher,
                    style: const TextStyle(color: Colors.grey, fontSize: 13),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TimePill extends StatelessWidget {
  final String time;
  const _TimePill(this.time);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: StudentTimetablePage.blue.withOpacity(0.08),
      ),
      child: Text(
        time.replaceAll('-', ' – '),
        style: const TextStyle(
          fontSize: 12,
          color: StudentTimetablePage.blue,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
