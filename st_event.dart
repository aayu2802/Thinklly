import 'package:flutter/material.dart';

class StEventScreen extends StatelessWidget {
  const StEventScreen({super.key});

  final List<Map<String, dynamic>> events = const [
    {
      "title": "Annual Sports Day",
      "date": "12 Feb 2026",
      "time": "9:00 AM - 3:00 PM",
      "venue": "School Ground",
      "description":
          "Get ready for an exciting day full of sports, competitions, and team spirit. Participation is mandatory for all students.",
      "isImportant": true,
    },
    {
      "title": "Science Exhibition",
      "date": "20 Feb 2026",
      "time": "10:00 AM - 1:00 PM",
      "venue": "Auditorium",
      "description":
          "Students will showcase innovative science projects and models. Parents are also invited.",
      "isImportant": false,
    },
    {
      "title": "Parent-Teacher Meeting",
      "date": "25 Feb 2026",
      "time": "11:00 AM - 2:00 PM",
      "venue": "Respective Classrooms",
      "description":
          "Discussion regarding academic progress and overall performance of students.",
      "isImportant": true,
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F7FB),
      appBar: AppBar(
        elevation: 0,
        centerTitle: true,
        title: const Text(
          "School Events",
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
        padding: const EdgeInsets.all(16),
        itemCount: events.length,
        itemBuilder: (context, index) {
          final event = events[index];

          return Container(
            margin: const EdgeInsets.only(bottom: 18),
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(22),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.06),
                  blurRadius: 20,
                  offset: const Offset(0, 10),
                ),
              ],
              border: Border.all(
                color: event['isImportant']
                    ? Colors.redAccent.withOpacity(0.6)
                    : Colors.transparent,
                width: 1.2,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                /// 🔹 Title + Important Badge
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        event['title'],
                        style: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    if (event['isImportant'])
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 5,
                        ),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(20),
                          color: Colors.redAccent.withOpacity(0.12),
                        ),
                        child: const Text(
                          "IMPORTANT",
                          style: TextStyle(
                            color: Colors.redAccent,
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                  ],
                ),

                const SizedBox(height: 14),

                _infoRow(Icons.calendar_today, event['date']),
                _infoRow(Icons.access_time, event['time']),
                _infoRow(Icons.location_on, event['venue']),

                const SizedBox(height: 12),

                Text(
                  event['description'],
                  style: const TextStyle(
                    color: Colors.black54,
                    fontSize: 13.5,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _infoRow(IconData icon, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(icon, size: 16, color: Color.fromARGB(255, 4, 89, 129)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 13,
                color: Colors.black87,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
