import 'package:flutter/material.dart';

class StFeedbackScreen extends StatefulWidget {
  const StFeedbackScreen({super.key});

  @override
  State<StFeedbackScreen> createState() => _StFeedbackScreenState();
}

class _StFeedbackScreenState extends State<StFeedbackScreen> {
  final TextEditingController _feedbackController = TextEditingController();

  double _rating = 0;
  String _selectedCategory = "School";
  bool _isAnonymous = false;
  bool _isSubmitting = false;

  final List<String> categories = [
    "School",
    "Teacher",
    "Transport",
    "Thinklly App",
  ];

  final Color darkTeal = const Color.fromARGB(255, 2, 50, 61);
  final Color blueTeal = const Color.fromARGB(255, 4, 89, 129);

  void _submitFeedback() async {
    if (_rating == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Please provide a rating ⭐"),
          backgroundColor: Colors.redAccent,
        ),
      );
      return;
    }

    if (_feedbackController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Please write your feedback"),
          backgroundColor: Colors.redAccent,
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    await Future.delayed(const Duration(seconds: 1));

    setState(() => _isSubmitting = false);

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text("Thank you for your feedback ❤️"),
        backgroundColor: Colors.green,
      ),
    );

    _feedbackController.clear();
    setState(() {
      _rating = 0;
      _selectedCategory = "School";
      _isAnonymous = false;
    });
  }

  @override
  void dispose() {
    _feedbackController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        elevation: 0,
        title: const Text(
          "Student Feedback",
          style: TextStyle(color: Colors.white),
        ),
        flexibleSpace: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [darkTeal, blueTeal]),
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(18),
        child: Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(18),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.08),
                blurRadius: 14,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                "We value your opinion ✨",
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              const Text(
                "Your feedback helps us improve your learning experience.",
                style: TextStyle(color: Colors.black54),
              ),

              const SizedBox(height: 20),

              // 🔹 Category Dropdown
              DropdownButtonFormField<String>(
                value: _selectedCategory,
                decoration: InputDecoration(
                  labelText: "Feedback Category",
                  filled: true,
                  fillColor: Colors.grey.shade50,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                items: categories
                    .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                    .toList(),
                onChanged: (value) {
                  setState(() => _selectedCategory = value!);
                },
              ),

              const SizedBox(height: 18),

              // ⭐ Rating
              const Text(
                "Rate your experience",
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              Row(
                children: List.generate(5, (index) {
                  return IconButton(
                    icon: Icon(
                      index < _rating ? Icons.star : Icons.star_border,
                      color: Colors.amber,
                      size: 30,
                    ),
                    onPressed: () {
                      setState(() => _rating = index + 1.0);
                    },
                  );
                }),
              ),

              const SizedBox(height: 14),

              // ✍ Feedback Text
              TextFormField(
                controller: _feedbackController,
                maxLines: 5,
                decoration: InputDecoration(
                  hintText: "Write your feedback here...",
                  filled: true,
                  fillColor: Colors.grey.shade50,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
              ),

              const SizedBox(height: 14),

              // 🔒 Anonymous toggle
              SwitchListTile(
                value: _isAnonymous,
                onChanged: (value) {
                  setState(() => _isAnonymous = value);
                },
                title: const Text("Submit as Anonymous"),
                subtitle: const Text(
                  "Your name will not be visible to teachers",
                  style: TextStyle(fontSize: 12),
                ),
                activeColor: blueTeal,
              ),

              const SizedBox(height: 22),

              // 🚀 Submit Button
              SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: _isSubmitting ? null : _submitFeedback,
                  style: ElevatedButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                    padding: EdgeInsets.zero,
                  ),
                  child: Ink(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [darkTeal, blueTeal]),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Center(
                      child: _isSubmitting
                          ? const SizedBox(
                              height: 22,
                              width: 22,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text(
                              "Submit Feedback",
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
