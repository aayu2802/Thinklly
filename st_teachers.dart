import 'package:flutter/material.dart';

class StTeacher extends StatefulWidget {
  const StTeacher({super.key});

  @override
  State<StTeacher> createState() => _StTeacherState();
}

class _StTeacherState extends State<StTeacher> {
  final List<Map<String, dynamic>> teachers = [
    {
      'name': 'Mr. Rajesh Sharma',
      'subjects': ['Mathematics', 'Physics'],
      'email': 'rajesh.sharma@example.com',
      'avatar': '👨‍🏫',
    },
    {
      'name': 'Ms. Priya Verma',
      'subjects': ['Chemistry', 'Biology'],
      'email': 'priya.verma@example.com',
      'avatar': '👩‍🏫',
    },
    {
      'name': 'Mr. Anil Kumar',
      'subjects': ['History', 'Geography'],
      'email': 'anil.kumar@example.com',
      'avatar': '👨‍🏫',
    },
    {
      'name': 'Ms. Neha Singh',
      'subjects': ['English', 'Hindi'],
      'email': 'neha.singh@example.com',
      'avatar': '👩‍🏫',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: const Text(
          'Teachers',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),

        centerTitle: true,
        backgroundColor: Color.fromARGB(255, 2, 50, 61),

        elevation: 0,
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: teachers.length,
        itemBuilder: (context, index) {
          final teacher = teachers[index];
          return GestureDetector(
            onTap: () => _showTeacherDialog(context, teacher),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [
                    Color.fromARGB(255, 2, 50, 61),
                    Color.fromARGB(255, 4, 89, 129),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(24),
                boxShadow: const [
                  BoxShadow(
                    color: Colors.black12,
                    blurRadius: 12,
                    offset: Offset(0, 6),
                  ),
                ],
              ),
              child: ListTile(
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 16,
                ),
                leading: CircleAvatar(
                  radius: 28,
                  backgroundColor: Colors.white.withOpacity(0.3),
                  child: Text(
                    teacher['avatar'],
                    style: const TextStyle(fontSize: 24),
                  ),
                ),
                title: Text(
                  teacher['name'],
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 18,
                    color: Colors.white,
                  ),
                ),
                subtitle: Padding(
                  padding: const EdgeInsets.only(top: 8.0),
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    children: List.generate(
                      teacher['subjects'].length,
                      (i) => Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [
                              Color.fromARGB(255, 2, 50, 61),
                              Color.fromARGB(255, 4, 89, 129),
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.circular(12),
                          boxShadow: const [
                            BoxShadow(
                              color: Colors.black26,
                              offset: Offset(0, 2),
                              blurRadius: 4,
                            ),
                          ],
                        ),
                        child: Text(
                          teacher['subjects'][i],
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                trailing: IconButton(
                  icon: const Icon(Icons.email, color: Colors.white),
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          'Email: ${teacher['email']} (dummy action)',
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  void _showTeacherDialog(BuildContext context, Map<String, dynamic> teacher) {
    showDialog(
      context: context,
      builder: (context) {
        return Dialog(
          backgroundColor: Colors.white.withOpacity(0.95),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircleAvatar(
                  radius: 40,
                  backgroundColor: const Color(0xFF4B7BE5),
                  child: Text(
                    teacher['avatar'],
                    style: const TextStyle(fontSize: 36),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  teacher['name'],
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  children: List.generate(
                    teacher['subjects'].length,
                    (i) => Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [
                            Color.fromARGB(255, 2, 50, 61),
                            Color.fromARGB(255, 4, 89, 129),
                          ],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: const [
                          BoxShadow(
                            color: Colors.black26,
                            offset: Offset(0, 2),
                            blurRadius: 4,
                          ),
                        ],
                      ),
                      child: Text(
                        teacher['subjects'][i],
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () {
                    Navigator.pop(context);
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Email: ${teacher['email']}')),
                    );
                  },
                  icon: const Icon(Icons.email),
                  label: const Text('Send Email'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4B7BE5),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
