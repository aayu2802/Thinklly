import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';

class StClassProgress extends StatelessWidget {
  const StClassProgress({super.key});

  // Dummy student data
  final List<Map<String, dynamic>> students = const [
    {
      'name': 'Aayushmann',
      'score': 95,
      'profile': 'https://i.pravatar.cc/150?img=3',
    },
    {
      'name': 'Rohan',
      'score': 88,
      'profile': 'https://i.pravatar.cc/150?img=5',
    },
    {
      'name': 'Priya',
      'score': 92,
      'profile': 'https://i.pravatar.cc/150?img=6',
    },
    {
      'name': 'Sneha',
      'score': 80,
      'profile': 'https://i.pravatar.cc/150?img=7',
    },
    {
      'name': 'Vikram',
      'score': 78,
      'profile': 'https://i.pravatar.cc/150?img=8',
    },
  ];

  @override
  Widget build(BuildContext context) {
    final sortedStudents = [...students];
    sortedStudents.sort((a, b) => b['score'].compareTo(a['score']));
    final topStudent = sortedStudents.first;

    return Scaffold(
      backgroundColor: const Color(0xFFF4F7FB),

      /// 🔹 AppBar with ERP Gradient
      appBar: AppBar(
        elevation: 0,
        centerTitle: true,
        title: const Text(
          'Class Progress',
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

      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            /// 🔹 Top Student Card
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [
                    Color.fromARGB(255, 2, 50, 61),
                    Color.fromARGB(255, 4, 89, 129),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(22),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.2),
                    blurRadius: 20,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 36,
                    backgroundImage: NetworkImage(topStudent['profile']),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Top Student',
                          style: TextStyle(color: Colors.white70, fontSize: 13),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          topStudent['name'],
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Score: ${topStudent['score']}%',
                          style: const TextStyle(
                            color: Colors.white70,
                            fontSize: 15,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Icon(Icons.emoji_events, color: Colors.amber, size: 38),
                ],
              ),
            ),

            const SizedBox(height: 26),

            /// 🔹 Bar Chart
            Expanded(
              child: Card(
                elevation: 6,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(22),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: BarChart(
                    BarChartData(
                      alignment: BarChartAlignment.spaceAround,
                      maxY: 100,
                      minY: 0,
                      groupsSpace: 22,
                      barTouchData: BarTouchData(
                        enabled: true,
                        touchTooltipData: BarTouchTooltipData(
                          getTooltipItem: (group, groupIndex, rod, rodIndex) {
                            final student = students[groupIndex];
                            return BarTooltipItem(
                              '${student['name']}\nScore: ${rod.toY.toInt()}%',
                              const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                              ),
                            );
                          },
                        ),
                      ),
                      titlesData: FlTitlesData(
                        bottomTitles: AxisTitles(
                          sideTitles: SideTitles(
                            showTitles: true,
                            reservedSize: 42,
                            getTitlesWidget: (value, meta) {
                              final index = value.toInt();
                              if (index >= 0 && index < students.length) {
                                return Padding(
                                  padding: const EdgeInsets.only(top: 8),
                                  child: Text(
                                    students[index]['name'],
                                    style: const TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                );
                              }
                              return const SizedBox();
                            },
                          ),
                        ),
                        leftTitles: AxisTitles(
                          sideTitles: SideTitles(
                            showTitles: true,
                            interval: 20,
                            reservedSize: 34,
                            getTitlesWidget: (value, meta) {
                              return Text(
                                '${value.toInt()}%',
                                style: const TextStyle(fontSize: 11),
                              );
                            },
                          ),
                        ),
                        topTitles: AxisTitles(
                          sideTitles: SideTitles(showTitles: false),
                        ),
                        rightTitles: AxisTitles(
                          sideTitles: SideTitles(showTitles: false),
                        ),
                      ),
                      gridData: FlGridData(show: true, horizontalInterval: 20),
                      borderData: FlBorderData(show: false),
                      barGroups: students
                          .asMap()
                          .entries
                          .map(
                            (e) => BarChartGroupData(
                              x: e.key,
                              barRods: [
                                BarChartRodData(
                                  toY: e.value['score'].toDouble(),
                                  width: 22,
                                  color: e.value == topStudent
                                      ? const Color.fromARGB(255, 4, 89, 129)
                                      : const Color.fromARGB(
                                          255,
                                          2,
                                          50,
                                          61,
                                        ).withOpacity(0.6),
                                  borderRadius: const BorderRadius.only(
                                    topLeft: Radius.circular(8),
                                    topRight: Radius.circular(8),
                                  ),
                                ),
                              ],
                            ),
                          )
                          .toList(),
                    ),
                    swapAnimationDuration: const Duration(milliseconds: 600),
                    swapAnimationCurve: Curves.easeInOut,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
