#ifndef UDP_POSITION_PROVIDER_HPP_PROTOVA
#define UDP_POSITION_PROVIDER_HPP_PROTOVA
#include <vanetza/common/position_provider.hpp>
#include <vanetza/common/runtime.hpp>
#include <boost/asio/io_context.hpp>
#include <boost/asio/ip/udp.hpp>
#include <array>
#include <cstddef>

// Fournisseur de position alimente par UDP : recoit des datagrammes "lat,lon"
// (degres) et met a jour la position courante. Permet une position DYNAMIQUE
// (poussee par un node ROS2) sans recompiler a chaque changement.
class UdpPositionProvider : public vanetza::PositionProvider
{
public:
    UdpPositionProvider(boost::asio::io_context&, const vanetza::Runtime&, unsigned port);
    const vanetza::PositionFix& position_fix() override;
private:
    void start_receive();
    boost::asio::ip::udp::socket socket_;
    boost::asio::ip::udp::endpoint sender_;
    std::array<char, 128> buffer_;
    const vanetza::Runtime& runtime_;
    vanetza::PositionFix fix_;
};
#endif
