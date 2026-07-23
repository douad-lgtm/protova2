#include "denm_application.hpp"
#include <vanetza/btp/ports.hpp>
#include <vanetza/asn1/denm.hpp>
#include <vanetza/asn1/packet_visitor.hpp>
#include <vanetza/facilities/cam_functions.hpp>
#include <vanetza/common/its_aid.hpp>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <stdexcept>

using namespace vanetza;
using namespace vanetza::facilities;
using namespace std::chrono;

DenmApplication::DenmApplication(PositionProvider& positioning, Runtime& rt,
        boost::asio::io_context& io, unsigned trigger_port) :
    positioning_(positioning), runtime_(rt),
    socket_(io, boost::asio::ip::udp::endpoint(boost::asio::ip::udp::v4(), trigger_port))
{
    start_receive();
    std::cout << "DENM: declencheur UDP en ecoute sur le port " << trigger_port
              << " (tout datagramme => 1 DENM emis)" << std::endl;
}

DenmApplication::PortType DenmApplication::port()
{
    return btp::ports::DENM;
}

void DenmApplication::set_station_id(std::uint32_t id) { station_id_ = id; }
void DenmApplication::set_cause(long c, long s) { cause_ = c; subcause_ = s; }
void DenmApplication::print_received_message(bool flag) { print_rx_msg_ = flag; }
void DenmApplication::print_generated_message(bool flag) { print_tx_msg_ = flag; }

void DenmApplication::start_receive()
{
    socket_.async_receive_from(boost::asio::buffer(buffer_), sender_,
        [this](const boost::system::error_code& ec, std::size_t n) {
            if (!ec && n > 0) {
                try {
                    trigger();
                } catch (const std::exception& e) {
                    std::cerr << "DENM trigger error: " << e.what() << std::endl;
                }
            }
            start_receive();
        });
}

void DenmApplication::indicate(const DataIndication&, UpPacketPtr packet)
{
    asn1::PacketVisitor<asn1::Denm> visitor;
    std::shared_ptr<const asn1::Denm> denm = boost::apply_visitor(visitor, *packet);

    std::cout << "DENM application received a packet with "
              << (denm ? "decodable" : "broken") << " content" << std::endl;
    if (denm && print_rx_msg_) {
        const auto& d = (*denm)->denm;
        long cause = d.situation ? d.situation->eventType.causeCode : -1;
        long sub = d.situation ? d.situation->eventType.subCauseCode : -1;
        std::cout << "Received DENM contains"
                  << "\n  Station ID: " << (*denm)->header.stationID
                  << "\n  Cause: " << cause
                  << "\n  SubCause: " << sub
                  << "\n  Latitude: " << d.management.eventPosition.latitude
                  << "\n  Longitude: " << d.management.eventPosition.longitude
                  << std::endl;
    }
}

void DenmApplication::trigger()
{
    auto position = positioning_.position_fix();
    if (!has_horizontal_position(position)) {
        std::cerr << "Skip DENM generation without position fix" << std::endl;
        return;
    }

    vanetza::asn1::Denm message;

    ItsPduHeader_t& header = message->header;
    header.protocolVersion = 2;
    header.messageID = ItsPduHeader__messageID_denm;
    header.stationID = station_id_;

    // --- Management (obligatoire) ---
    ManagementContainer_t& mgmt = message->denm.management;
    mgmt.actionID.originatingStationID = station_id_;
    mgmt.actionID.sequenceNumber = seq_++;
    const auto now_ms = duration_cast<milliseconds>(runtime_.now().time_since_epoch()).count();
    asn_uint642INTEGER(&mgmt.detectionTime, now_ms);
    asn_uint642INTEGER(&mgmt.referenceTime, now_ms);
    mgmt.stationType = StationType_passengerCar;
    copy(position, mgmt.eventPosition);

    // --- Situation (optionnel) : la CAUSE de l'alerte ---
    SituationContainer_t* sit =
        static_cast<SituationContainer_t*>(calloc(1, sizeof(SituationContainer_t)));
    sit->informationQuality = 7;
    sit->eventType.causeCode = cause_;
    sit->eventType.subCauseCode = subcause_;
    message->denm.situation = sit;

    std::string error;
    if (!message.validate(error)) {
        throw std::runtime_error("Invalid DENM: " + error);
    }

    if (print_tx_msg_) {
        std::cout << "Generated DENM contains"
                  << "\n  Station ID: " << station_id_
                  << "\n  Cause: " << cause_
                  << "\n  SubCause: " << subcause_ << std::endl;
    }

    DownPacketPtr packet { new DownPacket() };
    packet->layer(OsiLayer::Application) = std::move(message);

    DataRequest request;
    request.its_aid = aid::DEN;
    request.transport_type = geonet::TransportType::SHB;
    request.communication_profile = geonet::CommunicationProfile::ITS_G5;

    auto confirm = Application::request(request, std::move(packet));
    if (!confirm.accepted()) {
        throw std::runtime_error("DENM application data request failed");
    }
    std::cout << "DENM emis (cause " << cause_ << "/" << subcause_
              << ", seq " << (seq_ - 1) << ")" << std::endl;
}
