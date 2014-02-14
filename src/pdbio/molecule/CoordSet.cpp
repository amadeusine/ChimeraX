// vim: set expandtab ts=4 sw=4:
#include "Atom.h"
#include "CoordSet.h"

#include <utility>  // for pair

CoordSet::CoordSet(int cs_id): _cs_id(cs_id)
{
}

CoordSet::CoordSet(int cs_id, int size): _cs_id(cs_id)
{
    _coords.reserve(size);
}

float
CoordSet::get_bfactor(const Atom *a) const
{
    std::map<const Atom *, float>::const_iterator bfi = _bfactor_map.find(a);
    if (bfi == _bfactor_map.end())
        return 0.0;
    return (*bfi).second;
}

float
CoordSet::get_occupancy(const Atom *a) const
{
    std::map<const Atom *, float>::const_iterator bfi = _occupancy_map.find(a);
    if (bfi == _occupancy_map.end())
        return 1.0;
    return (*bfi).second;
}

void
CoordSet::set_bfactor(const Atom *a, float val)
{
    _bfactor_map.insert(std::pair<const Atom *, float>(a, val));
}

void
CoordSet::set_occupancy(const Atom *a, float val)
{
    _occupancy_map.insert(std::pair<const Atom *, float>(a, val));
}
