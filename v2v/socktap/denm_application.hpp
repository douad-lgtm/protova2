#ifndef DENM_APPLICATION_HPP_PROTOVA
#define DENM_APPLICATION_HPP_PROTOVA
#include "application.hpp"
#include <vanetza/common/position_provider.hpp>
#include <vanetza/common/runtime.hpp>
#include <boost/asio/io_context.hpp>
#include <boost/asio/ip/udp.hpp>
#include <array>
#include <cstdint>

// Application DENM pour socktap (ProtoVA).
// Emet un DENM (message d'evenement ETSI = alerte) sur COMMANDE recue par UDP
// (declenchee par ROS quand /obstacle/brake passe a True) et AFFICHE les DENM
// recus. Calquee sur CamApplication. Un DENM porte une cause (ex. situation
// dangereuse / freinage d'urgence) et la position de l'evenement.
class DenmApplication : public Application
{
public:
    DenmApplication(vanetza::PositionProvider& positioning, vanetza::Runtime& rt,
                    boost::asio::io_context& io, unsigned trigger_port);
    PortType port() override;
    void indicate(const DataIndication&, UpPacketPtr) override;
    void set_station_id(std::uint32_t station_id);
    void set_cause(long cause, long subcause);
    void print_received_message(bool flag);
    void print_generated_message(bool flag);
    void trigger();                 // construit et emet un DENM immediatement

private:
    void start_receive();           // ecoute UDP -> chaque datagramme declenche un DENM

    vanetza::PositionProvider& positioning_;
    vanetza::Runtime& runtime_;
    boost::asio::ip::udp::socket socket_;
    boost::asio::ip::udp::endpoint sender_;
    std::array<char, 64> buffer_;
    std::uint32_t station_id_ = 1;
    long cause_ = 99;               // dangerousSituation
    long subcause_ = 2;             // emergencyElectronicBrakeEngaged
    std::uint16_t seq_ = 0;
    bool print_rx_msg_ = false;
    bool print_tx_msg_ = false;
};
#endif /* DENM_APPLICATION_HPP_PROTOVA */
