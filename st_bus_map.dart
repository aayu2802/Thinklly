import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

class StBusMapScreen extends StatelessWidget {
  final Map<String, dynamic> bus;

  const StBusMapScreen({super.key, required this.bus});

  @override
  Widget build(BuildContext context) {
    // 🔴 Mock live bus location (API se aayega later)
    final LatLng busLocation = const LatLng(28.4089, 77.3178);
    final LatLng schoolLocation = const LatLng(28.4229, 77.3125);

    return Scaffold(
      appBar: AppBar(
        title: Text("${bus["bus_no"]} Live Tracking"),
        backgroundColor: Colors.indigo,
      ),
      body: GoogleMap(
        initialCameraPosition: CameraPosition(target: busLocation, zoom: 14),
        markers: {
          Marker(
            markerId: const MarkerId("bus"),
            position: busLocation,
            infoWindow: InfoWindow(
              title: bus["bus_no"],
              snippet: "Current Location",
            ),
            icon: BitmapDescriptor.defaultMarkerWithHue(
              BitmapDescriptor.hueBlue,
            ),
          ),
          const Marker(
            markerId: MarkerId("school"),
            position: LatLng(28.4229, 77.3125),
            infoWindow: InfoWindow(title: "School"),
          ),
        },
        polylines: {
          Polyline(
            polylineId: const PolylineId("route"),
            points: [busLocation, schoolLocation],
            color: Colors.indigo,
            width: 5,
          ),
        },
        zoomControlsEnabled: false,
      ),
    );
  }
}
