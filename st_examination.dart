import 'package:flutter/material.dart';

class StudentExaminationPage extends StatelessWidget {
  const StudentExaminationPage({super.key});

  // Thinklly Theme
  static const Color blue = Color(0xFF1E5EFF);
  static const Color green = Color(0xFF00C897);
  static const Color bg = Color(0xFFF6F8FC);

  static const List<Map<String, dynamic>> exams = [
    {
      'subject': 'Mathematics',
      'type': 'Unit Test',
      'date': '25 Feb 2026',
      'time': '09:00 - 10:00',
      'duration': '1 Hour',
      'marks': '25',
      'mode': 'Written',
      'room': 'Room 204',
      'syllabus': 'Ch 5 to 7',
      'status': 'upcoming',
    },
    {
      'subject': 'Physics',
      'type': 'Mid Term',
      'date': '28 Feb 2026',
      'time': '10:00 - 12:00',
      'duration': '2 Hours',
      'marks': '50',
      'mode': 'Written',
      'room': 'Room 301',
      'syllabus': 'Electricity & Magnetism',
      'status': 'upcoming',
    },
    {
      'subject': 'Chemistry',
      'type': 'Weekly Test',
      'date': '15 Feb 2026',
      'time': '09:00 - 10:00',
      'duration': '1 Hour',
      'marks': '20',
      'mode': 'Written',
      'room': 'Lab 2',
      'syllabus': 'Acids & Bases',
      'status': 'completed',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        elevation: 0,
        centerTitle: true,
        title: const Text(
          'Examination',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),

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
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(20),
        itemCount: exams.length,
        itemBuilder: (context, index) {
          final exam = exams[index];
          return _ExamCard(exam);
        },
      ),
    );
  }
}

// ================= Exam Card =================
class _ExamCard extends StatelessWidget {
  final Map<String, dynamic> exam;
  const _ExamCard(this.exam);

  bool get isUpcoming => exam['status'] == 'upcoming';

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 22),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: isUpcoming
            ? Border.all(color: StudentExaminationPage.green, width: 1.4)
            : null,
        boxShadow: [
          BoxShadow(
            color: isUpcoming
                ? StudentExaminationPage.green.withOpacity(0.22)
                : Colors.black.withOpacity(0.06),
            blurRadius: 22,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          /// Header
          Row(
            children: [
              _Chip(text: exam['type'], color: StudentExaminationPage.blue),
              const Spacer(),
              _StatusChip(isUpcoming),
            ],
          ),

          const SizedBox(height: 14),

          /// Subject
          Text(
            exam['subject'],
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
          ),

          const SizedBox(height: 14),

          /// Date & Time
          _InfoRow(Icons.calendar_today, exam['date']),
          _InfoRow(Icons.access_time, exam['time']),
          _InfoRow(Icons.timer, exam['duration']),
          _InfoRow(Icons.school, 'Room: ${exam['room']}'),

          const SizedBox(height: 14),

          /// Marks + Mode
          Row(
            children: [
              _SmallBox('Marks', exam['marks']),
              const SizedBox(width: 12),
              _SmallBox('Mode', exam['mode']),
            ],
          ),

          const SizedBox(height: 14),

          /// Syllabus
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.menu_book, size: 16, color: Colors.grey),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Syllabus: ${exam['syllabus']}',
                  style: const TextStyle(fontSize: 13, color: Colors.grey),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ================= Widgets =================
class _Chip extends StatelessWidget {
  final String text;
  final Color color;
  const _Chip({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: color.withOpacity(0.08),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 12,
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  final bool upcoming;
  const _StatusChip(this.upcoming);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: LinearGradient(
          colors: upcoming
              ? [StudentExaminationPage.green, StudentExaminationPage.blue]
              : [Colors.grey.shade400, Colors.grey.shade500],
        ),
      ),
      child: Text(
        upcoming ? 'UPCOMING' : 'COMPLETED',
        style: const TextStyle(
          color: Colors.white,
          fontSize: 11,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String text;
  const _InfoRow(this.icon, this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(icon, size: 16, color: Colors.grey),
          const SizedBox(width: 8),
          Text(text, style: const TextStyle(fontSize: 13, color: Colors.grey)),
        ],
      ),
    );
  }
}

class _SmallBox extends StatelessWidget {
  final String title;
  final String value;
  const _SmallBox(this.title, this.value);

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          color: StudentExaminationPage.blue.withOpacity(0.06),
        ),
        child: Column(
          children: [
            Text(
              title,
              style: const TextStyle(fontSize: 11, color: Colors.grey),
            ),
            const SizedBox(height: 4),
            Text(
              value,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  }
}
