import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:pdf/widgets.dart' as pw; // PDF package
import 'package:printing/printing.dart'; // For printing/sharing PDF

class StFeePayment extends StatefulWidget {
  const StFeePayment({super.key});

  @override
  State<StFeePayment> createState() => _StFeePaymentState();
}

class _StFeePaymentState extends State<StFeePayment> {
  // Dummy data for fees
  final List<Map<String, dynamic>> fees = [
    {
      'title': 'Tuition Fee - Jan 2026',
      'amount': 15000,
      'dueDate': DateTime(2026, 01, 31),
      'status': 'Pending',
    },
    {
      'title': 'Lab Fee - Jan 2026',
      'amount': 3000,
      'dueDate': DateTime(2026, 01, 25),
      'status': 'Paid',
    },
    {
      'title': 'Tuition Fee - Feb 2026',
      'amount': 15000,
      'dueDate': DateTime(2026, 02, 28),
      'status': 'Pending',
    },
    {
      'title': 'Library Fee - Jan 2026',
      'amount': 1000,
      'dueDate': DateTime(2026, 01, 20),
      'status': 'Overdue',
    },
  ];

  // Calculate fee progress
  double getFeeProgress() {
    if (fees.isEmpty) return 0;
    int paidCount = fees.where((fee) => fee['status'] == 'Paid').length;
    return paidCount / fees.length;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: const Text(
          'Fee Payment',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),

        centerTitle: true,
        backgroundColor: Color.fromARGB(255, 2, 50, 61),

        elevation: 0,
      ),
      body: Column(
        children: [
          // Fee progress bar
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Fee Payment Progress',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    Text(
                      '${(getFeeProgress() * 100).toStringAsFixed(0)}%',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: getFeeProgress(),
                  backgroundColor: Colors.grey[300],
                  color: const Color(0xFF4B7BE5),
                  minHeight: 8,
                ),
              ],
            ),
          ),

          // Fee list
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              itemCount: fees.length,
              itemBuilder: (context, index) {
                final fee = fees[index];
                final dueDate = fee['dueDate'] as DateTime;
                final isOverdue =
                    dueDate.isBefore(DateTime.now()) && fee['status'] != 'Paid';

                Color statusColor;
                if (fee['status'] == 'Paid') {
                  statusColor = Colors.green;
                } else if (isOverdue) {
                  statusColor = Colors.redAccent;
                } else {
                  statusColor = Colors.orangeAccent;
                }

                return GestureDetector(
                  onTap: () => _showFeeDetailsDialog(context, fee),
                  child: Container(
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
                      boxShadow: const [
                        BoxShadow(
                          color: Colors.black12,
                          offset: Offset(0, 4),
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
                        fee['title'],
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
                              'Amount: ₹${NumberFormat('#,###').format(fee['amount'])}',
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 14,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Due: ${dueDate.day}-${dueDate.month}-${dueDate.year}',
                              style: TextStyle(
                                color: isOverdue
                                    ? Colors.red[200]
                                    : Colors.white70,
                                fontSize: 14,
                              ),
                            ),
                            const SizedBox(height: 4),
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
                                fee['status'],
                                style: TextStyle(
                                  color: statusColor,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      trailing:
                          fee['status'] == 'Pending' ||
                              fee['status'] == 'Overdue'
                          ? ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.white,
                                foregroundColor: const Color(0xFF4B7BE5),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                              ),
                              onPressed: () {
                                _payFee(fee);
                              },
                              child: const Text('Pay Now'),
                            )
                          : ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.white,
                                foregroundColor: Colors.green,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                              ),
                              onPressed: () {
                                _generatePdfReceipt(fee);
                              },
                              child: const Text('Download Receipt'),
                            ),
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

  // Fee details dialog with Download Receipt button
  void _showFeeDetailsDialog(BuildContext context, Map<String, dynamic> fee) {
    final dueDate = fee['dueDate'] as DateTime;
    final isOverdue =
        dueDate.isBefore(DateTime.now()) && fee['status'] != 'Paid';

    Color statusColor;
    if (fee['status'] == 'Paid') {
      statusColor = Colors.green;
    } else if (isOverdue) {
      statusColor = Colors.redAccent;
    } else {
      statusColor = Colors.orangeAccent;
    }

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          title: Text(fee['title']),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Amount: ₹${NumberFormat('#,###').format(fee['amount'])}'),
              const SizedBox(height: 8),
              Text('Due Date: ${dueDate.day}-${dueDate.month}-${dueDate.year}'),
              const SizedBox(height: 8),
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
                  fee['status'],
                  style: TextStyle(
                    color: statusColor,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
            if (fee['status'] != 'Paid')
              ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  _payFee(fee);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF4B7BE5),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('Pay Now'),
              ),
            if (fee['status'] == 'Paid')
              ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  _generatePdfReceipt(fee);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('Download Receipt'),
              ),
          ],
        );
      },
    );
  }

  // Dummy payment handler
  void _payFee(Map<String, dynamic> fee) {
    setState(() {
      fee['status'] = 'Paid';
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('${fee['title']} paid successfully!'),
        backgroundColor: const Color(0xFF4B7BE5),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  // Generate PDF receipt
  void _generatePdfReceipt(Map<String, dynamic> fee) async {
    final pdf = pw.Document();

    pdf.addPage(
      pw.Page(
        build: (pw.Context context) {
          return pw.Center(
            child: pw.Column(
              mainAxisAlignment: pw.MainAxisAlignment.center,
              children: [
                pw.Text(
                  'Fee Receipt',
                  style: pw.TextStyle(
                    fontSize: 24,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                pw.SizedBox(height: 20),
                pw.Text('Title: ${fee['title']}'),
                pw.Text(
                  'Amount Paid: ₹${NumberFormat('#,###').format(fee['amount'])}',
                ),
                pw.Text(
                  'Date: ${DateFormat('dd-MM-yyyy').format(DateTime.now())}',
                ),
                pw.Text('Status: ${fee['status']}'),
                pw.SizedBox(height: 20),
                pw.Text(
                  'Thank you for your payment!',
                  style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
                ),
              ],
            ),
          );
        },
      ),
    );

    // Open the PDF in a viewer or share/save
    await Printing.layoutPdf(onLayout: (format) async => pdf.save());
  }
}
