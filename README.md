# Home Assistant Blinds Control Integration

Upgrade your Home Assistant with this custom blinds control integration. It's designed to effortlessly manage your time-based blinds, syncing with your chosen entities for raising and lowering. Plus, it remembers your settings after restarts and supports tilting.

## How to Install

Getting started is a piece of cake!

You can add this integration through HACS (Home Assistant Community Store) as a custom repository, or simply copy all files from the custom_components/blinds_controller directory into your Home Assistant's /custom_components/blinds_controller/ directory. 

Then, just give Home Assistant a quick restart, and you're good to go.

## Setting Things Up

Head over to Settings -> Devices and Services -> Click on Add Integration (select Blinds Control) to integrate your blinds into the system.

Name your blinds, select the controlling entities, specify roll-up and roll-down times in seconds, and if you need it, set tilt times (or leave them at 0 if you don't want to tilt support).

You can also tweak existing configurations to suit your preferences (just reload the edited entries).

## Automations
During the setup process, you have the option to configure various automated tasks. These features are currently in an EXPERIMENTAL phase and are being developed as part of my bachelor's thesis, so please refrain from extensive experimentation with this automation.

Examples include scheduling specific times for actions such as raising or lowering blinds, automating the opening and closing of blinds based on sunrise and sunset times, or automatically lowering blinds when a particular entity is activated during the night. Additionally, there are weather protection measures available, such as responding to strong winds using the [WMO Code](https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM) and utilizing the [Open Meteo API](https://open-meteo.com/) or perhaps you would like to use Netatmo, that also works.  For those utilizing interlock relays, there's the possibility of triggering a stop command at the end of travel.

## Need Help?

Got a snag? Visit [GitHub issues page](https://github.com/MatthewOnTour/BUT_blinds_time_control/issues) to report any issues or seek assistance or head over to documentation [GitHub documentation](https://github.com/MatthewOnTour/BUT_blinds_time_control/blob/main/README.md).

## Acknowledgment

Work was based on and inspired by this insightful [community post](https://community.home-assistant.io/t/custom-component-cover-time-based/187654)

## Support

You can support my work here: 

<a href="https://www.buymeacoffee.com/MatthewOnTour"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" width="200" /></a>


## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/MatthewOnTour/BUT_blinds_time_control?tab=MIT-1-ov-file) file for details.

