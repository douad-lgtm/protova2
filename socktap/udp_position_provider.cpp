#include "udp_position_provider.hpp"
#include <vanetza/units/angle.hpp>
#include <vanetza/units/length.hpp>
#include <vanetza/units/velocity.hpp>
#include <cmath>
#include <cstdio>
#include <string>

using namespace vanetza;
namespace ip = boost::asio::ip;

// Origine des caps : Nord vrai a 0 degre.
static const units::TrueNorth north = units::TrueNorth::from_value(0.0);

UdpPositionProvider::UdpPositionProvider(boost::asio::io_context& io, const Runtime& rt, unsigned port) :
    socket_(io, ip::udp::endpoint(ip::udp::v4(), port)),
    runtime_(rt)
{
    fix_.timestamp = runtime_.now();
    fix_.latitude = 0.0 * units::degree;
    fix_.longitude = 0.0 * units::degree;
    fix_.confidence.semi_major = 5.0 * units::si::meter;
    fix_.confidence.semi_minor = 5.0 * units::si::meter;
    start_receive();
}

const PositionFix& UdpPositionProvider::position_fix()
{
    return fix_;
}

void UdpPositionProvider::start_receive()
{
    socket_.async_receive_from(boost::asio::buffer(buffer_), sender_,
        [this](const boost::system::error_code& ec, std::size_t n) {
            if (!ec && n > 0) {
                std::string s(buffer_.data(), n);
                // Datagramme "lat,lon" ou "lat,lon,cap,vitesse"
                // (cap en degres Nord vrai, vitesse en m/s).
                double lat = 0.0, lon = 0.0, hdg = 0.0, spd = 0.0;
                int got = std::sscanf(s.c_str(), "%lf,%lf,%lf,%lf", &lat, &lon, &hdg, &spd);
                if (got >= 2) {
                    fix_.timestamp = runtime_.now();
                    fix_.latitude = lat * units::degree;
                    fix_.longitude = lon * units::degree;
                }
                if (got >= 4) {
                    double h = std::fmod(hdg, 360.0);
                    if (h < 0.0) h += 360.0;
                    fix_.course.assign(north + h * units::degree,
                                       north + 1.0 * units::degree);
                    if (spd < 0.0) spd = 0.0;
                    fix_.speed.assign(spd * units::si::meter_per_second,
                                      0.1 * units::si::meter_per_second);
                }
            }
            start_receive();
        });
}
