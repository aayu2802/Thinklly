import 'package:app/st_bus_map.dart';
import 'package:flutter/material.dart';

class StTransportScreen extends StatefulWidget {
  const StTransportScreen({super.key});

  @override
  State<StTransportScreen> createState() => _StTransportScreenState();
}

class _StTransportScreenState extends State<StTransportScreen> {
  // 🔹 Mock transport data (later API se replace kar sakte ho)
  final List<Map<String, dynamic>> buses = [
    {
      "bus_no": "BUS-12",
      "route": "Sector 21 → NIT → School",
      "driver": "Ramesh Kumar",
      "contact": "9876543210",
      "status": "On Time",
      "assigned": true,
    },
    {
      "bus_no": "BUS-07",
      "route": "Old Faridabad → Ajronda → School",
      "driver": "Suresh Yadav",
      "contact": "9123456789",
      "status": "Delayed",
      "assigned": false,
    },
    {
      "bus_no": "BUS-18",
      "route": "Ballabhgarh → Sector 15 → School",
      "driver": "Mahesh Singh",
      "contact": "9988776655",
      "status": "On Time",
      "assigned": false,
    },
  ];

  Color _statusColor(String status) {
    return status == "On Time" ? Colors.green : Colors.redAccent;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F7FB),

      /// 🔹 AppBar with ERP Gradient
      appBar: AppBar(
        elevation: 0,
        title: const Text(
          'Transport',
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
      ),

      body: ListView.builder(
        padding: const EdgeInsets.all(14),
        itemCount: buses.length,
        itemBuilder: (context, index) {
          final bus = buses[index];

          return Container(
            margin: const EdgeInsets.only(bottom: 16),
            decoration: BoxDecoration(
              color: bus["assigned"]
                  ? const Color.fromARGB(255, 4, 89, 129).withOpacity(0.08)
                  : Colors.white,
              borderRadius: BorderRadius.circular(18),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.08),
                  blurRadius: 18,
                  offset: const Offset(0, 8),
                ),
              ],
              border: Border.all(
                color: bus["assigned"]
                    ? const Color.fromARGB(255, 4, 89, 129)
                    : Colors.grey.shade300,
                width: bus["assigned"] ? 1.2 : 0.8,
              ),
            ),

            /// 🔹 Expansion Tile
            child: ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 10,
              ),

              leading: CircleAvatar(
                radius: 22,
                backgroundColor: const Color.fromARGB(255, 4, 89, 129),
                child: const Icon(Icons.directions_bus, color: Colors.white),
              ),

              title: Text(
                bus["bus_no"],
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
              ),

              subtitle: Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(bus["route"], style: const TextStyle(fontSize: 13)),
              ),

              trailing: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: _statusColor(bus["status"]).withOpacity(0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(
                  bus["status"],
                  style: TextStyle(
                    color: _statusColor(bus["status"]),
                    fontWeight: FontWeight.w600,
                    fontSize: 12,
                  ),
                ),
              ),

              children: [
                const Divider(height: 1),

                const SizedBox(height: 8),
                _infoRow("Driver", bus["driver"]),
                _infoRow("Contact", bus["contact"]),
                const SizedBox(height: 12),

                /// 🔥 Live Tracking Button
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => StBusMapScreen(bus: bus),
                          ),
                        );
                      },
                      icon: const Icon(Icons.location_on, color: Colors.white),
                      label: const Text(
                        "Track Live",
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        backgroundColor: const Color.fromARGB(255, 4, 89, 129),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        elevation: 4,
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 14),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _infoRow(String title, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: [
          Text(
            "$title: ",
            style: const TextStyle(
              fontWeight: FontWeight.w600,
              color: Colors.black87,
            ),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(color: Colors.black54)),
          ),
        ],
      ),
    );
  }
}
