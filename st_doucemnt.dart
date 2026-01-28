import 'package:flutter/material.dart';

class StDocumentScreen extends StatelessWidget {
  const StDocumentScreen({super.key});

  // 🔹 Mock documents (future me API se aa sakta hai)
  static final List<Map<String, dynamic>> documents = [
    {
      "title": "Aadhaar Card",
      "type": "PDF",
      "icon": Icons.picture_as_pdf,
      "color": Colors.redAccent,
      "uploaded_on": "12 Jan 2026",
    },
    {
      "title": "Marksheet",
      "type": "PDF",
      "icon": Icons.assignment,
      "color": Colors.indigo,
      "uploaded_on": "05 Feb 2026",
    },
    {
      "title": "Birth Certificate",
      "type": "Image",
      "icon": Icons.image,
      "color": Colors.green,
      "uploaded_on": "20 Dec 2025",
    },
    {
      "title": "Fee Receipt",
      "type": "PDF",
      "icon": Icons.receipt_long,
      "color": Colors.orange,
      "uploaded_on": "01 Feb 2026",
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F8FC),
      appBar: AppBar(
        elevation: 0,
        centerTitle: true,
        title: const Text(
          "My Documents",
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
        padding: const EdgeInsets.all(14),
        child: GridView.builder(
          itemCount: documents.length,
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            crossAxisSpacing: 14,
            mainAxisSpacing: 14,
            childAspectRatio: 0.85,
          ),
          itemBuilder: (context, index) {
            final doc = documents[index];

            return Container(
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.08),
                    blurRadius: 14,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const SizedBox(height: 14),

                  /// 🔹 Icon
                  CircleAvatar(
                    radius: 32,
                    backgroundColor: doc["color"].withOpacity(0.12),
                    child: Icon(doc["icon"], color: doc["color"], size: 34),
                  ),

                  /// 🔹 Title & date
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    child: Column(
                      children: [
                        Text(
                          doc["title"],
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          "Uploaded: ${doc["uploaded_on"]}",
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontSize: 11,
                            color: Colors.black54,
                          ),
                        ),
                      ],
                    ),
                  ),

                  /// 🔹 Download button
                  Padding(
                    padding: const EdgeInsets.all(10),
                    child: SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text("${doc["title"]} downloading..."),
                            ),
                          );
                        },
                        icon: const Icon(
                          Icons.download,
                          size: 18,
                          color: Colors.white,
                        ),
                        label: const Text(
                          "Download",
                          style: TextStyle(color: Colors.white),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color.fromARGB(
                            255,
                            4,
                            89,
                            129,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
