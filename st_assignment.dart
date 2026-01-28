import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class StAssignment extends StatefulWidget {
  const StAssignment({super.key});

  @override
  State<StAssignment> createState() => _StAssignmentState();
}

class _StAssignmentState extends State<StAssignment> {
  // Dummy data for assignments
  final List<Map<String, dynamic>> assignments = [
    {
      'title': 'Math Assignment 1',
      'subject': 'Mathematics',
      'dueDate': DateTime.now().add(Duration(days: 3)),
      'status': 'Pending',
      'teacherRemark': 'Focus on algebra',
    },
    {
      'title': 'Physics Lab Report',
      'subject': 'Physics',
      'dueDate': DateTime.now().subtract(Duration(days: 1)),
      'status': 'Submitted',
      'teacherRemark': 'Good work',
    },
    {
      'title': 'History Essay',
      'subject': 'History',
      'dueDate': DateTime.now().add(Duration(days: 5)),
      'status': 'Pending',
      'teacherRemark': 'Cite sources properly',
    },
    {
      'title': 'Chemistry Assignment',
      'subject': 'Chemistry',
      'dueDate': DateTime.now().add(Duration(days: 2)),
      'status': 'Submitted',
      'teacherRemark': 'Well done!',
    },
  ];

  // Function to calculate assignment progress
  double getProgress() {
    if (assignments.isEmpty) return 0.0;
    int submittedCount = assignments
        .where((assignment) => assignment['status'] == 'Submitted')
        .length;
    return submittedCount / assignments.length;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: const Text(
          'Assignments',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),

        centerTitle: true,
        backgroundColor: Color.fromARGB(255, 2, 50, 61),
        elevation: 0,
      ),
      body: Column(
        children: [
          // Progress indicator
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Assignment Progress',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    Text(
                      '${(getProgress() * 100).toStringAsFixed(0)}%',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: getProgress(),
                  backgroundColor: Colors.grey[300],
                  color: Color.fromARGB(255, 4, 89, 129),
                  minHeight: 8,
                ),
              ],
            ),
          ),

          // Calendar / upcoming due dates horizontal list
          Container(
            height: 90,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: assignments.length,
              itemBuilder: (context, index) {
                final assignment = assignments[index];
                final dueDate = assignment['dueDate'] as DateTime;
                final isOverdue =
                    dueDate.isBefore(DateTime.now()) &&
                    assignment['status'] != 'Submitted';

                return Container(
                  width: 80,
                  margin: const EdgeInsets.only(right: 12),
                  decoration: BoxDecoration(
                    color: isOverdue ? Colors.red[300] : Colors.blue[200],
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black12,
                        blurRadius: 6,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        DateFormat('d MMM').format(dueDate),
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        assignment['title'],
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                );
              },
            ),
          ),

          const SizedBox(height: 12),

          // Assignment list
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: assignments.length,
              itemBuilder: (context, index) {
                final assignment = assignments[index];
                final dueDate = assignment['dueDate'] as DateTime;
                final isOverdue =
                    dueDate.isBefore(DateTime.now()) &&
                    assignment['status'] != 'Submitted';

                Color statusColor = assignment['status'] == 'Submitted'
                    ? Colors.green
                    : isOverdue
                    ? Colors.redAccent
                    : Colors.orangeAccent;

                return Container(
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
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black12,
                        offset: const Offset(0, 4),
                        blurRadius: 10,
                      ),
                    ],
                  ),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 20,
                      vertical: 16,
                    ),
                    title: Text(
                      assignment['title'],
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 18,
                        color: Colors.white,
                      ),
                    ),
                    subtitle: Padding(
                      padding: const EdgeInsets.only(top: 8.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Subject: ${assignment['subject']}',
                            style: const TextStyle(color: Colors.white70),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Due: ${dueDate.day}-${dueDate.month}-${dueDate.year}',
                            style: TextStyle(
                              color: isOverdue
                                  ? Colors.red[200]
                                  : Colors.white70,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: statusColor.withOpacity(0.2),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Text(
                                  assignment['status'],
                                  style: TextStyle(
                                    color: statusColor,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  'Remark: ${assignment['teacherRemark']}',
                                  style: const TextStyle(color: Colors.white70),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    trailing: assignment['status'] == 'Pending'
                        ? ElevatedButton.icon(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.white,
                              foregroundColor: Color.fromARGB(255, 2, 50, 61),

                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                            icon: const Icon(Icons.upload_file, size: 18),
                            label: const Text('Submit'),
                            onPressed: () {
                              _showSubmitDialog(context, assignment['title']);
                            },
                          )
                        : const Icon(
                            Icons.check_circle,
                            color: Colors.white,
                            size: 28,
                          ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  // Submit dialog with dummy file upload
  void _showSubmitDialog(BuildContext context, String title) {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          title: Text('Submit Assignment'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Do you want to submit "$title"?'),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: () {
                  // Dummy file upload logic
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('File selected (dummy upload)'),
                    ),
                  );
                },
                icon: const Icon(Icons.attach_file),
                label: const Text('Upload File'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF4B7BE5),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(context);
              },
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF4B7BE5),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              onPressed: () {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('"$title" submitted successfully!'),
                    behavior: SnackBarBehavior.floating,
                    backgroundColor: const Color(0xFF4B7BE5),
                  ),
                );
              },
              child: const Text('Submit'),
            ),
          ],
        );
      },
    );
  }
}
